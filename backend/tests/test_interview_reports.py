"""Task 2 结构化面试评估与报告 API 的验收测试。

覆盖：
- TR-2.1 面试完成后报告落库且 7 维度完整；
- TR-2.2 LLM 非法 JSON / 异常时降级路径不抛错、报告仍落库（total_score=None）；
- TR-2.3 报告建议转复习任务，source=report，落在最近未完成日；
- TR-2.4 候选人模式到达轮次上限后 completed=true 并生成提问质量报告。
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.core.agent_loop import AgentLoop
from interview_agent.core.config import InterviewConfig, InterviewMode
from interview_agent.core.harness import LangChainInterviewHarness, ScriptedInterviewHarness
from interview_agent.infrastructure.db.models import (
    Base,
    InterviewReportModel,
    InterviewSessionModel,
    ReviewDayModel,
    ReviewPlanModel,
    ReviewProgressModel,
    ReviewTaskModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.services.interview_report_service import InterviewReportService

TENANT = "default"
USER = "anonymous"
LONG_ANSWER = (
    "我在项目里负责 RAG 召回链路的设计与上线，自己做了召回率评测集，"
    "离线指标从 82% 提升到 92%，线上故障时做了降级和告警复盘。"
)


def _register_headers(client: TestClient, email: str) -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": f"198.51.100.{ip_suffix}"},
        json={"email": email, "password": "passw0rd!", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def _run_interview_to_completion(max_turns: int = 1) -> tuple[InterviewConfig, object]:
    config = InterviewConfig(max_turns=max_turns)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()
    result = None
    for _ in range(max_turns + 2):
        result = loop.step(LONG_ANSWER)
        if result.state.completed:
            break
    assert result.state.completed is True
    return config, result


async def _seed_session(factory, *, mode: str = "interviewer") -> str:
    session_id = str(uuid.uuid4())
    async with factory() as db:
        db.add(
            InterviewSessionModel(
                id=uuid.UUID(session_id),
                tenant_id=TENANT,
                user_id=USER,
                mode=mode,
                industry="internet",
                candidate_name="张三",
                target_role="AI 应用工程师",
                seniority="中级",
            )
        )
        await db.commit()
    return session_id


# ---- TR-2.1 ----
@pytest.mark.asyncio
async def test_report_persisted_on_completion_with_seven_dimensions(db_factory):
    config, result = _run_interview_to_completion(max_turns=1)
    session_id = await _seed_session(db_factory)

    async with db_factory() as db:
        service = InterviewReportService(db, tenant_id=TENANT, user_id=USER)
        report = await service.persist_evaluation(
            session_id=session_id, config=config, evaluation=result.evaluation
        )
        await db.commit()

    assert report["total_score"] == 72
    assert report["mode"] == "interviewer"
    expected_dims = {
        "technical_depth",
        "communication",
        "problem_solving",
        "role_fit",
        "resume_truthfulness",
        "ai_engineering",
        "agent_frameworks",
    }
    assert set(report["dimension_scores"].keys()) == expected_dims
    assert len(report["suggestions"]) == 3
    assert report["strength_tags"] and report["weakness_tags"]
    assert report["summary"]

    async with db_factory() as db:
        rows = (await db.execute(InterviewReportModel.__table__.select())).all()
        assert len(rows) == 1
        assert rows[0].total_score == 72


# ---- TR-2.2 ----
class _FakeLLM:
    def __init__(self, content: str, *, raises: bool = False):
        self.content_store = content
        self.raises = raises

    def invoke(self, messages):
        if self.raises:
            raise RuntimeError("llm unavailable")

        class _Response:
            pass

        response = _Response()
        response.content = self.content_store
        response.usage_metadata = None
        response.response_metadata = None
        return response


def _lang_harness_with_fake_llm(fake_llm):
    config = InterviewConfig()
    harness = LangChainInterviewHarness.__new__(LangChainInterviewHarness)
    harness.config = config
    harness.guardrails = ScriptedInterviewHarness(config).guardrails
    harness.knowledge_base = None
    harness.web_search = None
    harness.llm = fake_llm
    return config, harness


@pytest.mark.asyncio
async def test_degraded_report_when_llm_returns_invalid_json(db_factory):
    config, harness = _lang_harness_with_fake_llm(_FakeLLM("这是一段纯文本评价，没有任何 JSON 结构。"))
    state = AgentLoop(config, harness).state
    result = harness.generate_evaluation_result(state)
    assert result.structured is not None
    assert result.structured["degraded"] is True
    assert result.structured["total_score"] is None
    assert result.text  # 仍有可读文本

    session_id = await _seed_session(db_factory)
    async with db_factory() as db:
        service = InterviewReportService(db, tenant_id=TENANT, user_id=USER)
        report = await service.persist_evaluation(
            session_id=session_id, config=config, evaluation=result.structured
        )
        await db.commit()
    assert report["total_score"] is None
    assert report["degraded"] is True
    assert report["summary"]


@pytest.mark.asyncio
async def test_degraded_report_when_llm_raises(db_factory):
    config, harness = _lang_harness_with_fake_llm(_FakeLLM("", raises=True))
    state = AgentLoop(config, harness).state
    result = harness.generate_evaluation_result(state)
    assert result.fallback_used is True
    assert result.structured["degraded"] is True
    assert result.structured["total_score"] is None
    assert result.text


# ---- TR-2.4 ----
@pytest.mark.asyncio
async def test_candidate_mode_completes_with_question_quality_report():
    config = InterviewConfig(mode=InterviewMode.CANDIDATE, max_turns=2)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()
    result = None
    for i in range(3):
        result = loop.step(f"请回答第 {i + 1} 道面试题：你如何设计 RAG 评测体系？请展开说明。")
        if result.state.completed:
            break
    assert result.state.completed is True
    assert result.evaluation is not None
    dims = result.evaluation["dimension_scores"]
    assert set(dims.keys()) == {"question_depth", "coverage", "differentiation"}
    assert result.evaluation["mode"] == "candidate"
    assert result.evaluation["total_score"] is not None


# ---- TR-2.3 ----
async def _seed_plan(factory) -> tuple[str, str, str]:
    """返回 (plan_id, day1_id, day2_id)；day1 任务全部完成，day2 未完成。"""
    async with factory() as db:
        plan = ReviewPlanModel(
            tenant_id=TENANT,
            user_id=USER,
            plan_key=f"plan-{uuid.uuid4().hex[:8]}",
            title="测试计划",
            start_date=date(2026, 9, 1),
            status="active",
        )
        db.add(plan)
        await db.flush()
        day1 = ReviewDayModel(
            plan_id=plan.id, tenant_id=TENANT, user_id=USER,
            day_key="day-01", day_label="第 1 天", sort_order=1,
            scheduled_date=date(2026, 9, 1),
        )
        day2 = ReviewDayModel(
            plan_id=plan.id, tenant_id=TENANT, user_id=USER,
            day_key="day-02", day_label="第 2 天", sort_order=2,
            scheduled_date=date(2026, 9, 2),
        )
        db.add_all([day1, day2])
        await db.flush()
        task1 = ReviewTaskModel(
            plan_id=plan.id, day_id=day1.id, tenant_id=TENANT, user_id=USER,
            task_key="t1", title="已完成任务", sort_order=1,
        )
        task2 = ReviewTaskModel(
            plan_id=plan.id, day_id=day2.id, tenant_id=TENANT, user_id=USER,
            task_key="t2", title="未完成任务", sort_order=1,
        )
        db.add_all([task1, task2])
        await db.flush()
        db.add(
            ReviewProgressModel(
                plan_id=plan.id, day_id=day1.id, task_id=task1.id,
                tenant_id=TENANT, user_id=USER, done=True,
            )
        )
        await db.commit()
        return str(plan.id), str(day1.id), str(day2.id)


@pytest.mark.asyncio
async def test_report_tasks_land_on_nearest_open_day(db_factory):
    config, result = _run_interview_to_completion(max_turns=1)
    session_id = await _seed_session(db_factory)
    plan_id, _day1_id, day2_id = await _seed_plan(db_factory)

    async with db_factory() as db:
        service = InterviewReportService(db, tenant_id=TENANT, user_id=USER)
        await service.persist_evaluation(
            session_id=session_id, config=config, evaluation=result.evaluation
        )
        outcome = await service.add_tasks_from_report(plan_id=plan_id, session_id=session_id)
        await db.commit()

    assert outcome["day_id"] == day2_id, "应落在最早的未完成日（day2）"
    assert len(outcome["created"]) == 3
    for item in outcome["created"]:
        assert item["source"] == "report"
        assert item["link_type"] == "interview"

    async with db_factory() as db:
        rows = (
            await db.execute(
                ReviewTaskModel.__table__.select().where(ReviewTaskModel.source == "report")
            )
        ).all()
        assert len(rows) == 3
        assert all(row.day_id == uuid.UUID(day2_id) for row in rows)
        assert all(row.source_ref == session_id for row in rows)
        assert all(row.critical == 1 for row in rows)


@pytest.mark.asyncio
async def test_report_tasks_404_when_report_missing(db_factory):
    plan_id, _, _ = await _seed_plan(db_factory)
    async with db_factory() as db:
        service = InterviewReportService(db, tenant_id=TENANT, user_id=USER)
        with pytest.raises(LookupError):
            await service.add_tasks_from_report(
                plan_id=plan_id, session_id=str(uuid.uuid4())
            )


# ---- TR-2.1/2.3 API 端到端：完成面试 -> 报告自动落库 -> 薄弱项回流 ----
def test_api_interview_completion_creates_report_and_report_tasks(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "reports-e2e@example.com")
        recharge = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "100", "external_order_id": "order-reports-1"},
        )
        assert recharge.status_code == 200

        imported = client.post("/review-site/import", headers=headers, json={"plan_only": True})
        assert imported.status_code == 200
        plans = client.get("/review-site/plans", headers=headers).json()
        plan_id = plans[0]["id"]
        plan = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        task_id = plan["days"][0]["tasks"][0]["id"]

        created = client.post(
            "/sessions", headers=headers, json={"offline": True, "plan_task_id": task_id}
        )
        assert created.status_code == 200, created.text
        session_id = created.json()["session_id"]

        completed = False
        for _ in range(10):
            response = client.post(
                f"/sessions/{session_id}/messages",
                headers=headers,
                json={"message": LONG_ANSWER},
            )
            assert response.status_code == 200, response.text
            if response.json().get("completed"):
                completed = True
                break
        assert completed is True

        reports_resp = client.get("/interview-reports", headers=headers)
        assert reports_resp.status_code == 200
        data = reports_resp.json()
        assert data["trend"]["total_reports"] == 1
        report = data["reports"][0]
        assert report["session_id"] == session_id
        assert len(report["dimension_scores"]) == 7
        assert report["total_score"] is not None

        detail = client.get(f"/interview-reports/{session_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["suggestions"]

        sessions = client.get("/sessions", headers=headers).json()
        assert sessions[0]["plan_task_id"] == task_id

        report_tasks = client.post(
            f"/review-site/plans/{plan_id}/report-tasks",
            headers=headers,
            json={"session_id": session_id},
        )
        assert report_tasks.status_code == 200, report_tasks.text
        created_tasks = report_tasks.json()["data"]["created"]
        assert len(created_tasks) == 3
        assert all(item["source"] == "report" for item in created_tasks)

        missing = client.post(
            f"/review-site/plans/{plan_id}/report-tasks",
            headers=headers,
            json={"session_id": str(uuid.uuid4())},
        )
        assert missing.status_code == 404

    asyncio.run(engine.dispose())
