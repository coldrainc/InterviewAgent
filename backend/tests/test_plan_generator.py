"""Task 6 LLM 个性化计划生成 + 天/任务/素材写接口测试。

覆盖：
- TR-6.1 LLM 结合简历/报告/错题生成计划：任务带 reason，模拟/刷题任务带可跳转 link；
- TR-6.2 LLM 异常/非法输出/离线时降级规则模板（API 200, generated_by=rule）；
- TR-6.3 天/任务/素材 CRUD 持久化，刷新后可读；
- TR-6.4 源码无 file:// 与 /Users/ 绝对路径。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

import interview_agent
from interview_agent.infrastructure.db.models import (
    Base,
    InterviewSessionModel,
    PracticeQuestionModel,
    ResumeModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces import api as api_module
from interview_agent.interfaces.api import create_app
from interview_agent.repositories.interview_report_repository import InterviewReportRepository
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.plan_generator_service import (
    PlanGeneratorService,
    _extract_json_object,
)

TENANT = "default"
USER = "anonymous"


def _llm_plan_payload(total_days: int = 5) -> str:
    days = []
    for day_index in range(1, total_days + 1):
        tasks = [
            {
                "title": f"第{day_index}天：项目深挖模拟",
                "kind": "simulation",
                "reason": "报告显示项目深挖是薄弱点，需要全真模拟暴露问题",
                "tags": ["模拟面试"],
                "mode": "candidate",
                "focus": "STAR 项目深挖",
                "critical": True,
            },
            {
                "title": f"第{day_index}天：专项刷题",
                "kind": "practice",
                "reason": "错题本中网络类题目反复出错",
                "tags": ["刷题"],
                "category": "internet",
            },
            {
                "title": f"第{day_index}天：复习笔记整理",
                "kind": "study",
                "reason": "当天内容需要沉淀",
                "tags": ["复习"],
            },
        ]
        days.append({
            "day_index": day_index,
            "phase": "p1" if day_index <= total_days // 2 else "p2",
            "title": f"第 {day_index} 天主题",
            "acceptance": f"完成第{day_index}天全部任务并复盘",
            "tasks": tasks,
        })
    return json.dumps({
        "phases": [
            {"key": "p1", "title": "基础巩固", "goal": "过一遍基础", "ratio": 0.5},
            {"key": "p2", "title": "模拟冲刺", "goal": "密集模拟", "ratio": 0.5},
        ],
        "days": days,
    }, ensure_ascii=False)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    def __init__(self, content: str | None = None, raises: bool = False) -> None:
        self.content = content
        self.raises = raises
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        if self.raises:
            raise RuntimeError("llm boom")
        return FakeResponse(self.content or "")


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


async def _seed_history(factory) -> str:
    """写入简历 + 一场已出报告的面试 + 一道错题，返回 resume_id。"""
    async with factory() as db:
        resume = ResumeModel(
            tenant_id=TENANT,
            user_id=USER,
            filename="resume.pdf",
            file_type="pdf",
            content_hash=uuid.uuid4().hex,
            summary="5 年前端工程师，熟悉 React/TypeScript，做过 Hybrid 容器与 AI Agent 项目。",
            text="简历全文……",
        )
        db.add(resume)
        await db.flush()

        session = InterviewSessionModel(
            tenant_id=TENANT,
            user_id=USER,
            mode="interviewer",
            industry="互联网",
            candidate_name="张三",
            target_role="前端工程师",
            seniority="高级",
            status="completed",
            resume_id=resume.id,
        )
        db.add(session)
        await db.flush()

        report_repo = InterviewReportRepository(db, tenant_id=TENANT, user_id=USER)
        await report_repo.upsert_report(
            session_id=session.id,
            mode="interviewer",
            total_score=62,
            dimension_scores={"基础": 3, "项目": 2},
            per_question=[],
            evidence=[],
            strength_tags=["表达清晰"],
            weakness_tags=["算法", "项目深挖"],
            suggestions=["加强算法练习", "项目 STAR 打磨"],
            summary_text="基础尚可，项目深挖不足。",
        )

        question = PracticeQuestionModel(
            tenant_id=TENANT,
            user_id=USER,
            practice_category="internet",
            prompt="HTTP/2 多路复用原理是什么？",
            content_hash=uuid.uuid4().hex,
            question_type="short_answer",
        )
        db.add(question)
        await db.flush()
        practice_repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        await practice_repo.touch_wrong_entry(question_id=question.id, is_correct=False)
        await db.commit()
        return str(resume.id)


# ---- TR-6.1 LLM 个性化生成 ----
@pytest.mark.asyncio
async def test_llm_generate_personalized_plan(db_factory) -> None:
    resume_id = await _seed_history(db_factory)
    async with db_factory() as db:
        llm = FakeLLM(content=_llm_plan_payload(5))
        service = PlanGeneratorService(
            db, tenant_id=TENANT, user_id=USER, llm=llm, model_id="fake-model"
        )
        result = await service.generate(
            title=None,
            target_role="前端工程师",
            seniority="高级",
            target_company="蚂蚁集团",
            total_days=5,
            hours_per_day=2.0,
            focus_areas=["算法", "项目深挖"],
            resume_id=resume_id,
        )
        assert result is not None
        assert result["generated_by"] == "llm"
        assert llm.calls == 1
        # 上下文确实进入了 prompt
        prompt = result["prompt_text"]
        assert "前端工程师" in prompt
        assert "算法" in prompt
        assert "项目深挖" in prompt  # 报告薄弱点
        assert "HTTP/2" in prompt  # 错题

        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        plan = await repo.get_plan(result["plan"].id)
        assert plan is not None
        assert plan.metadata_json.get("generated_by") == "llm"
        days = await repo.list_days(plan.id)
        assert len(days) == 5
        all_tasks = [task for day in days for task in day.tasks]
        assert len(all_tasks) >= 10
        # 每个任务都有 reason
        assert all(task.reason for task in all_tasks)
        # 模拟任务带可跳转 link
        sim_tasks = [t for t in all_tasks if t.link_type == "interview"]
        assert sim_tasks
        assert sim_tasks[0].link_payload_json.get("mode") == "candidate"
        assert sim_tasks[0].simulation is True
        assert sim_tasks[0].link_payload_json.get("focus")
        # 刷题任务带分类 link
        practice_tasks = [t for t in all_tasks if t.link_type == "practice"]
        assert practice_tasks
        assert practice_tasks[0].link_payload_json.get("category") == "internet"
        # breakdown 天数合计正确
        assert sum(item["days"] for item in result["breakdown"]) == 5


@pytest.mark.asyncio
async def test_llm_generate_pads_missing_days(db_factory) -> None:
    async with db_factory() as db:
        # LLM 只返回 3 天，要求 7 天 → 自动补齐
        llm = FakeLLM(content=_llm_plan_payload(3))
        service = PlanGeneratorService(
            db, tenant_id=TENANT, user_id=USER, llm=llm, model_id="fake"
        )
        result = await service.generate(
            title=None,
            target_role="后端",
            seniority="",
            target_company=None,
            total_days=7,
            hours_per_day=2.0,
            focus_areas=[],
        )
        assert result is not None
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        days = await repo.list_days(result["plan"].id)
        assert len(days) == 7
        assert all(day.tasks for day in days)


# ---- TR-6.2 降级 ----
@pytest.mark.asyncio
async def test_llm_failure_returns_none(db_factory) -> None:
    kwargs = dict(
        title=None, target_role="前端", seniority="高级", target_company=None,
        total_days=5, hours_per_day=2.0, focus_areas=[],
    )
    async with db_factory() as db:
        assert await PlanGeneratorService(
            db, tenant_id=TENANT, user_id=USER, llm=None
        ).generate(**kwargs) is None

        assert await PlanGeneratorService(
            db, tenant_id=TENANT, user_id=USER, llm=FakeLLM(raises=True), model_id="fake"
        ).generate(**kwargs) is None

        assert await PlanGeneratorService(
            db, tenant_id=TENANT, user_id=USER,
            llm=FakeLLM(content="抱歉，我无法输出 JSON。"), model_id="fake",
        ).generate(**kwargs) is None


def test_extract_json_object() -> None:
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json_object('好的，计划如下：{"a": 2}，请查收')["a"] == 2
    assert _extract_json_object("not json") is None
    assert _extract_json_object("") is None


# ---- API ----
def _register_headers(client: TestClient, email: str) -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    ip = f"198.51.100.{ip_suffix}"
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": ip},
        json={"email": email, "password": "passw0rd!", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Forwarded-For": ip,
    }


def _make_app(tmp_path):
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="planner-api")
    return engine, create_app(object_storage=storage, database_engine=engine)


def test_api_generate_falls_back_to_rule_when_offline(monkeypatch, tmp_path) -> None:
    engine, app = _make_app(tmp_path)
    monkeypatch.setattr(api_module, "_build_planner_llm", lambda: (None, "fake"))
    with TestClient(app) as client:
        headers = _register_headers(client, "planner-rule@example.com")
        resp = client.post(
            "/review-site/planner/generate",
            headers=headers,
            json={"target_role": "后端工程师", "total_days": 7, "hours_per_day": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["generated_by"] == "rule"
        detail = client.get(f"/review-site/plans/{body['plan_id']}", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["days"]) == 7


def test_api_generate_with_fake_llm(monkeypatch, tmp_path) -> None:
    engine, app = _make_app(tmp_path)
    fake_llm = FakeLLM(content=_llm_plan_payload(5))
    monkeypatch.setattr(api_module, "_build_planner_llm", lambda: (fake_llm, "fake-model"))
    with TestClient(app) as client:
        headers = _register_headers(client, "planner-llm@example.com")
        recharge = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "100", "external_order_id": "planner-llm-1"},
        )
        assert recharge.status_code == 200
        resp = client.post(
            "/review-site/planner/generate",
            headers=headers,
            json={
                "target_role": "前端工程师",
                "seniority": "高级",
                "target_company": "蚂蚁",
                "total_days": 5,
                "hours_per_day": 2,
                "focus_areas": ["算法"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["generated_by"] == "llm"
        detail = client.get(f"/review-site/plans/{body['plan_id']}", headers=headers).json()
        assert len(detail["days"]) == 5
        tasks = [task for day in detail["days"] for task in day["tasks"]]
        assert all(task["reason"] for task in tasks)
        assert any(task["link_type"] == "interview" for task in tasks)
        assert any(task["link_type"] == "practice" for task in tasks)


# ---- TR-6.3 CRUD ----
def test_api_day_task_material_crud(monkeypatch, tmp_path) -> None:
    engine, app = _make_app(tmp_path)
    monkeypatch.setattr(api_module, "_build_planner_llm", lambda: (None, "fake"))
    with TestClient(app) as client:
        headers = _register_headers(client, "planner-crud@example.com")
        gen = client.post(
            "/review-site/planner/generate",
            headers=headers,
            json={"target_role": "前端", "total_days": 7, "hours_per_day": 2},
        )
        plan_id = gen.json()["plan_id"]

        # 新建天
        created_day = client.post(
            f"/review-site/plans/{plan_id}/days",
            headers=headers,
            json={"title": "自定义加练日", "phase_key": "p3", "acceptance": "完成一场模拟"},
        )
        assert created_day.status_code == 201
        day_id = created_day.json()["id"]

        # 更新天
        patched_day = client.patch(
            f"/review-site/days/{day_id}",
            headers=headers,
            json={"title": "冲刺加练日", "scheduled_date": "2026-09-20"},
        )
        assert patched_day.status_code == 200
        assert patched_day.json()["title"] == "冲刺加练日"
        assert patched_day.json()["scheduled_date"] == "2026-09-20"

        # 新建任务（带刷题 link）
        created_task = client.post(
            f"/review-site/days/{day_id}/tasks",
            headers=headers,
            json={
                "title": "刷 20 道网络题",
                "link_type": "practice",
                "link_payload": {"category": "internet"},
                "reason": "网络是薄弱点",
                "tags": ["刷题"],
            },
        )
        assert created_task.status_code == 201
        task_id = created_task.json()["id"]
        assert created_task.json()["link_type"] == "practice"

        # 更新任务
        patched_task = client.patch(
            f"/review-site/tasks/{task_id}",
            headers=headers,
            json={"title": "刷 30 道网络题", "critical": True},
        )
        assert patched_task.status_code == 200
        assert patched_task.json()["title"] == "刷 30 道网络题"
        assert patched_task.json()["critical"] is True

        # 刷新计划详情，天与任务可读
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        day_titles = [day["title"] for day in detail["days"]]
        assert "冲刺加练日" in day_titles
        added_day = next(day for day in detail["days"] if day["id"] == day_id)
        assert any(task["id"] == task_id for task in added_day["tasks"])

        # 删除任务
        deleted_task = client.delete(f"/review-site/tasks/{task_id}", headers=headers)
        assert deleted_task.status_code == 200
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        added_day = next(day for day in detail["days"] if day["id"] == day_id)
        assert all(task["id"] != task_id for task in added_day["tasks"])

        # 素材：新建自我介绍稿
        created_script = client.post(
            f"/review-site/plans/{plan_id}/materials/intro_scripts",
            headers=headers,
            json={"label": "90 秒自我介绍", "text": "大家好，我是……", "duration_seconds": 90},
        )
        assert created_script.status_code == 201
        script_id = created_script.json()["id"]
        patched_script = client.patch(
            f"/review-site/materials/intro_scripts/{script_id}",
            headers=headers,
            json={"label": "60 秒自我介绍", "duration_seconds": 60},
        )
        assert patched_script.status_code == 200
        assert patched_script.json()["label"] == "60 秒自我介绍"
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        assert any(item["id"] == script_id for item in detail["intro_scripts"])

        # 素材：STAR 卡片
        created_card = client.post(
            f"/review-site/plans/{plan_id}/materials/star_cards",
            headers=headers,
            json={"title": "Hybrid 容器项目", "tag": "跨端", "background": "性能问题"},
        )
        assert created_card.status_code == 201
        card_id = created_card.json()["id"]
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        assert any(item["id"] == card_id for item in detail["star_cards"])

        # 素材：A4 速记
        created_a4 = client.post(
            f"/review-site/plans/{plan_id}/materials/a4_memory",
            headers=headers,
            json={"content": "TCP 三次握手：SYN/SYN-ACK/ACK", "side": "FRONT"},
        )
        assert created_a4.status_code == 201
        a4_id = created_a4.json()["id"]

        # 删除素材
        assert client.delete(f"/review-site/materials/intro_scripts/{script_id}", headers=headers).status_code == 200
        assert client.delete(f"/review-site/materials/star_cards/{card_id}", headers=headers).status_code == 200
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        assert all(item["id"] != script_id for item in detail["intro_scripts"])
        assert all(item["id"] != card_id for item in detail["star_cards"])
        # A4 速记仍在
        assert any(item["id"] == a4_id for item in detail.get("a4_memory", []))
        assert client.delete(f"/review-site/materials/a4_memory/{a4_id}", headers=headers).status_code == 200

        # 非法 kind → 400
        bad = client.post(
            f"/review-site/plans/{plan_id}/materials/unknown",
            headers=headers,
            json={"title": "x"},
        )
        assert bad.status_code == 400

        # 删除天
        assert client.delete(f"/review-site/days/{day_id}", headers=headers).status_code == 200
        detail = client.get(f"/review-site/plans/{plan_id}", headers=headers).json()
        assert all(day["id"] != day_id for day in detail["days"])

        # 不存在资源 → 404
        assert client.patch("/review-site/days/non-existent", headers=headers, json={"title": "x"}).status_code == 404
        assert client.delete("/review-site/tasks/non-existent", headers=headers).status_code == 404


# ---- TR-6.4 无 file:// 与本机绝对路径 ----
def test_no_file_url_or_absolute_paths() -> None:
    src_root = Path(interview_agent.__file__).parent
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "file://" in text or "/Users/" in text:
            offenders.append(str(path))
    assert not offenders, f"发现 file:// 或 /Users/ 绝对路径: {offenders}"
