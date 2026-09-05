"""Task 3 刷题作答落库与错题自动闭环测试。

覆盖：
- TR-3.1 作答落 practice_attempts、答错自动收录错题本且计数正确；
- TR-3.2 连对 mastery_level 上升、答错回落、达阈值标记 mastered；
- TR-3.3 v1 civil_service_questions 迁移到 v2 practice_questions 后总量一致、幂等；
- TR-3.4 wrong-book 的 mark_type/mastery/category/keyword 筛选与返回集合一致；
- 主观题 LLM 评分接入与异常降级；
- API 端到端：attempt 路由、错题本、404。
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    CivilServiceQuestionModel,
    PracticeAttemptModel,
    PracticeQuestionModel,
    UserAccountModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.services.civil_service_migration import migrate_civil_service_questions
from interview_agent.services.practice_attempt_service import PracticeAttemptService

TENANT = "default"
USER = "anonymous"


def _choice_question(prompt: str = "下列说法正确的是？", category: str = "civil_service") -> dict:
    return {
        "practice_category": category,
        "subject": "行测",
        "question_type": "single_choice",
        "prompt": prompt,
        "choices": ["选项甲", "选项乙", "选项丙", "选项丁"],
        "answer": "A",
        "answer_detail": "解析：甲正确，因为题干限定条件。",
        "difficulty": "medium",
        "tags": ["言语理解"],
    }


def _open_question(prompt: str = "请简述 RAG 召回率如何评测。") -> dict:
    return {
        "practice_category": "internet",
        "subject": "AI 工程",
        "question_type": "open",
        "prompt": prompt,
        "choices": [],
        "answer": "构建评测集，统计召回率@k，做人工标注与badcase分析。",
        "answer_detail": "参考答案：先建标注评测集，再算 Recall@k 与 MRR，按 badcase 分类优化。",
        "difficulty": "hard",
        "tags": ["RAG"],
    }


@pytest_asyncio.fixture
async def db_factory():
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_question(factory, payload: dict) -> str:
    async with factory() as db:
        repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        question, _ = await repo.upsert_question(**payload)
        await db.commit()
        return question["id"]


# ---- TR-3.1 作答落库 + 错题自动收录 ----
@pytest.mark.asyncio
async def test_wrong_choice_attempt_persists_and_auto_collects(db_factory) -> None:
    question_id = await _seed_question(db_factory, _choice_question())
    async with db_factory() as db:
        service = PracticeAttemptService(db, tenant_id=TENANT, user_id=USER)
        result = await service.submit_attempt(
            question_id=question_id, answer="B", elapsed_seconds=42
        )

        assert result["correct"] is False
        assert result["score"] == 0
        assert result["graded_by"] == "rule"
        assert result["in_wrong_book"] is True
        wrong = result["wrong_book"]
        assert wrong["mark_type"] == "wrong"
        assert wrong["attempt_count"] == 1
        assert wrong["correct_count"] == 0
        assert wrong["mastery_level"] == 0

        rows = (await db.execute(select(PracticeAttemptModel))).scalars().all()
        assert len(rows) == 1
        assert rows[0].elapsed_seconds == 42
        assert rows[0].is_correct is False
        assert rows[0].question_type == "single_choice"


# ---- TR-3.2 连对升级 / 答错回落 ----
@pytest.mark.asyncio
async def test_mastery_rises_on_consecutive_correct_and_falls_on_wrong(db_factory) -> None:
    question_id = await _seed_question(db_factory, _choice_question())
    async with db_factory() as db:
        service = PracticeAttemptService(db, tenant_id=TENANT, user_id=USER)

        r1 = await service.submit_attempt(question_id=question_id, answer="B")
        assert r1["wrong_book"]["mastery_level"] == 0
        assert r1["wrong_book"]["mark_type"] == "wrong"

        r2 = await service.submit_attempt(question_id=question_id, answer="A")
        assert r2["wrong_book"]["mastery_level"] == 1

        r3 = await service.submit_attempt(question_id=question_id, answer="A")
        assert r3["wrong_book"]["mastery_level"] == 2
        assert r3["can_remove_from_wrong_book"] is False

        r4 = await service.submit_attempt(question_id=question_id, answer="A")
        assert r4["wrong_book"]["mastery_level"] == 3
        assert r4["wrong_book"]["mark_type"] == "mastered"
        assert r4["can_remove_from_wrong_book"] is True

        r5 = await service.submit_attempt(question_id=question_id, answer="C")
        assert r5["wrong_book"]["mastery_level"] == 2
        assert r5["wrong_book"]["mark_type"] == "wrong"
        assert r5["wrong_book"]["attempt_count"] == 5
        assert r5["wrong_book"]["correct_count"] == 3


# ---- TR-3.1 答对不新建错题本 ----
@pytest.mark.asyncio
async def test_correct_attempt_does_not_create_wrong_entry(db_factory) -> None:
    question_id = await _seed_question(db_factory, _choice_question())
    async with db_factory() as db:
        service = PracticeAttemptService(db, tenant_id=TENANT, user_id=USER)
        result = await service.submit_attempt(question_id=question_id, answer="A")
        assert result["correct"] is True
        assert result["wrong_book"] is None
        assert result["in_wrong_book"] is False


# ---- 主观题 LLM 评分接入 ----
@pytest.mark.asyncio
async def test_subjective_llm_grader_used(db_factory) -> None:
    question_id = await _seed_question(db_factory, _open_question())
    calls: list[dict] = []

    async def fake_grader(question: dict, answer: str) -> dict:
        calls.append({"question": question["id"], "answer": answer})
        return {"score": 90, "feedback": "要点完整，结构清晰。", "suggestions": ["补充量化指标"]}

    async with db_factory() as db:
        service = PracticeAttemptService(
            db, tenant_id=TENANT, user_id=USER, subjective_grader=fake_grader
        )
        result = await service.submit_attempt(
            question_id=question_id, answer="我会先构建标注评测集，统计 Recall@k，再做 badcase 分析。"
        )
        assert len(calls) == 1
        assert result["graded_by"] == "llm"
        assert result["score"] == 90
        assert result["feedback"] == "要点完整，结构清晰。"
        assert result["suggestions"] == ["补充量化指标"]


# ---- 主观题 LLM 异常降级关键词判分 ----
@pytest.mark.asyncio
async def test_subjective_grader_failure_falls_back_to_keyword(db_factory) -> None:
    question_id = await _seed_question(db_factory, _open_question())

    async def boom(question: dict, answer: str) -> dict:
        raise RuntimeError("llm unavailable")

    async with db_factory() as db:
        service = PracticeAttemptService(
            db, tenant_id=TENANT, user_id=USER, subjective_grader=boom
        )
        result = await service.submit_attempt(
            question_id=question_id, answer="构建评测集，统计召回率@k，人工标注，badcase分析。"
        )
        assert result["graded_by"] == "keyword"
        assert 0 <= result["score"] <= 100


# ---- TR-3.3 v1 -> v2 迁移 ----
@pytest.mark.asyncio
async def test_migrate_v1_civil_questions_to_v2(db_factory) -> None:
    async with db_factory() as db:
        db.add_all([
            CivilServiceQuestionModel(
                id=uuid.uuid4(),
                tenant_id=TENANT,
                user_id=USER,
                practice_category="civil_service",
                source="seed",
                exam_year=2024,
                exam_name="国考",
                subject="行测",
                question_type="single_choice",
                prompt="v1 题目一",
                choices_json=["甲", "乙"],
                answer="A",
                explanation="v1 解析一",
                difficulty="easy",
                tags_json=["常识"],
                content_hash="v1-hash-1",
            ),
            CivilServiceQuestionModel(
                id=uuid.uuid4(),
                tenant_id=TENANT,
                user_id=USER,
                practice_category="civil_service",
                source="seed",
                exam_year=2023,
                exam_name="省考",
                subject="申论",
                question_type="open",
                prompt="v1 题目二",
                choices_json=[],
                answer="参考答案二",
                explanation="v1 解析二",
                difficulty="hard",
                tags_json=[],
                content_hash="v1-hash-2",
            ),
        ])
        await db.flush()

        stats = await migrate_civil_service_questions(db)
        assert stats["scanned"] == 2
        assert stats["created"] == 2

        repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        items, total = await repo.list_questions(limit=50)
        assert total == 2
        by_prompt = {item["prompt"]: item for item in items}
        assert by_prompt["v1 题目一"]["answer_detail"] == "v1 解析一"
        assert by_prompt["v1 题目一"]["choices"] == ["甲", "乙"]
        assert by_prompt["v1 题目一"]["metadata"]["migrated_from"] == "civil_service_questions"
        assert by_prompt["v1 题目一"]["metadata"]["exam_year"] == 2024

        # 幂等：再跑一次全部更新、总量不变
        stats_again = await migrate_civil_service_questions(db)
        assert stats_again["created"] == 0
        assert stats_again["updated"] == 2
        _, total_again = await repo.list_questions(limit=50)
        assert total_again == 2


# ---- TR-3.4 错题本筛选 ----
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs,expected_prompts",
    [
        (
            {},
            {"言语题甲：下列正确的是？", "RAG 召回题乙：向量库怎么选？", "资料题丙：增长率如何计算？"},
        ),
        (
            {"mark_type": "wrong"},
            {"言语题甲：下列正确的是？", "RAG 召回题乙：向量库怎么选？", "资料题丙：增长率如何计算？"},
        ),
        ({"mark_type": "mastered"}, set()),
        ({"category": "civil_service"}, {"言语题甲：下列正确的是？", "资料题丙：增长率如何计算？"}),
        ({"keyword": "RAG"}, {"RAG 召回题乙：向量库怎么选？"}),
        (
            {"mastery_max": 0},
            {"言语题甲：下列正确的是？", "RAG 召回题乙：向量库怎么选？", "资料题丙：增长率如何计算？"},
        ),
    ],
)
async def test_wrong_book_filters(db_factory, kwargs, expected_prompts) -> None:
    q1 = _choice_question(prompt="言语题甲：下列正确的是？", category="civil_service")
    q2 = _choice_question(prompt="RAG 召回题乙：向量库怎么选？", category="internet")
    q3 = _choice_question(prompt="资料题丙：增长率如何计算？", category="civil_service")
    ids = []
    for payload in (q1, q2, q3):
        ids.append(await _seed_question(db_factory, payload))

    async with db_factory() as db:
        service = PracticeAttemptService(db, tenant_id=TENANT, user_id=USER)
        for question_id in ids:
            await service.submit_attempt(question_id=question_id, answer="B")
        repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        entries = await repo.list_wrong_book(**kwargs)
        prompts = {entry["prompt"] for entry in entries}
        assert prompts == expected_prompts


# ---- API 端到端 ----
def _register_headers(client: TestClient, email: str) -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": f"198.51.100.{ip_suffix}"},
        json={"email": email, "password": "passw0rd!", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_practice_attempt_end_to_end(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="practice-api")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "practice-e2e@example.com")

        import asyncio

        async def _seed() -> str:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as db:
                account = (
                    await db.execute(
                        select(UserAccountModel).where(
                            UserAccountModel.email == "practice-e2e@example.com"
                        )
                    )
                ).scalar_one()
                question = PracticeQuestionModel(
                    id=uuid.uuid4(),
                    tenant_id=account.tenant_id,
                    user_id=account.user_id,
                    content_hash="api-choice-hash-1",
                    practice_category="civil_service",
                    subject="行测",
                    question_type="single_choice",
                    prompt="API 端到端选择题",
                    choices_json=["甲", "乙", "丙", "丁"],
                    answer="A",
                    answer_detail="解析：甲。",
                    difficulty="easy",
                    tags_json=[],
                    metadata_json={},
                )
                db.add(question)
                await db.commit()
                return str(question.id)

        question_id = asyncio.run(_seed())

        # 答错 -> 自动收录错题本
        wrong = client.post(
            f"/review-site/practice-questions/{question_id}/attempt",
            headers=headers,
            json={"answer": "B", "elapsed_seconds": 12},
        )
        assert wrong.status_code == 200, wrong.text
        body = wrong.json()
        assert body["correct"] is False
        assert body["wrong_book"]["mark_type"] == "wrong"
        assert body["wrong_book"]["attempt_count"] == 1

        # 作答历史
        attempts = client.get(
            f"/review-site/practice-questions/{question_id}/attempts", headers=headers
        )
        assert attempts.status_code == 200
        assert len(attempts.json()) == 1
        assert attempts.json()[0]["elapsed_seconds"] == 12

        # 错题本列表带题干
        wrong_book = client.get("/review-site/wrong-book", headers=headers)
        assert wrong_book.status_code == 200
        entries = wrong_book.json()
        assert len(entries) == 1
        assert entries[0]["prompt"] == "API 端到端选择题"
        assert entries[0]["practice_category"] == "civil_service"

        # 筛选生效
        filtered = client.get("/review-site/wrong-book?keyword=不存在的关键词", headers=headers)
        assert filtered.status_code == 200
        assert filtered.json() == []

        # 不存在的题目 404
        missing = client.post(
            f"/review-site/practice-questions/{uuid.uuid4()}/attempt",
            headers=headers,
            json={"answer": "A"},
        )
        assert missing.status_code == 404

    asyncio.run(engine.dispose())
