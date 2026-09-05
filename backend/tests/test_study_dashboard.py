"""Task 5 学习驾驶舱聚合测试。

覆盖：
- TR-5.1 固定数据集下 streak/今日任务/时长/面试/刷题/计划完成率/薄弱点与直接统计一致；
- TR-5.2 LLM 建议失败时降级规则文案且正常返回；
- 空数据冷启动；API 端到端 200。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    InterviewReportModel,
    InterviewSessionModel,
    PracticeQuestionModel,
    ReviewDayModel,
    ReviewPlanModel,
    ReviewTaskModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.repositories.interview_report_repository import InterviewReportRepository
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.repositories.review_checkin_repository import ReviewCheckinRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.practice_attempt_service import PracticeAttemptService
from interview_agent.services.study_dashboard_service import StudyDashboardService

TENANT = "default"
USER = "anonymous"


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


async def _seed_active_plan(factory, today: date) -> uuid.UUID:
    async with factory() as db:
        plan = ReviewPlanModel(
            tenant_id=TENANT, user_id=USER, plan_key=f"plan-{uuid.uuid4().hex[:8]}",
            title="冲刺计划", status="draft",
        )
        db.add(plan)
        await db.flush()
        day = ReviewDayModel(
            plan_id=plan.id, tenant_id=TENANT, user_id=USER,
            day_key="day-01", sort_order=1, scheduled_date=today,
        )
        db.add(day)
        await db.flush()
        for index in range(2):
            db.add(
                ReviewTaskModel(
                    plan_id=plan.id, day_id=day.id, tenant_id=TENANT, user_id=USER,
                    task_key=f"t-{index}", title=f"任务{index}", sort_order=index + 1,
                )
            )
        await db.commit()
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        await repo.update_plan(plan.id, {"status": "active", "start_date": today.isoformat()})
        days = await repo.list_days(plan.id)
        task = sorted(days[0].tasks, key=lambda t: t.sort_order)[0]
        await repo.update_progress(task.id, {"done": True, "elapsed_minutes": 25})
        await ReviewCheckinRepository(db, tenant_id=TENANT, user_id=USER).upsert_checkin(
            plan.id, today, tasks_done=1, total_tasks=2, elapsed_minutes=30, note="打卡"
        )
        await db.commit()
        return plan.id


async def _seed_practice(factory) -> None:
    async with factory() as db:
        repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        question, _ = await repo.upsert_question(
            practice_category="civil_service",
            subject="行测",
            question_type="single_choice",
            prompt="驾驶舱测试选择题",
            choices=["甲", "乙", "丙", "丁"],
            answer="A",
            answer_detail="解析",
            difficulty="easy",
        )
        service = PracticeAttemptService(db, tenant_id=TENANT, user_id=USER)
        await service.submit_attempt(question_id=question["id"], answer="A", elapsed_seconds=60)
        await service.submit_attempt(question_id=question["id"], answer="B", elapsed_seconds=120)
        await db.commit()


async def _seed_report(factory) -> None:
    async with factory() as db:
        session_id = uuid.uuid4()
        db.add(
            InterviewSessionModel(
                id=session_id,
                tenant_id=TENANT,
                user_id=USER,
                mode="interviewer",
                industry="互联网",
                candidate_name="考生",
                target_role="AI 工程师",
                seniority="3-5 年",
                status="completed",
            )
        )
        await db.flush()
        await InterviewReportRepository(db, tenant_id=TENANT, user_id=USER).upsert_report(
            session_id=session_id,
            mode="interviewer",
            total_score=72,
            dimension_scores={"technical_depth": 3},
            per_question=[],
            evidence=[],
            strength_tags=["沟通清晰"],
            weakness_tags=["RAG 召回", "系统设计"],
            suggestions=[{"category": "rag", "detail": "补召回评测"}],
            summary_text="总体不错",
            metadata_json={"verdict": "weak"},
        )
        await db.commit()


# ---- TR-5.1 固定数据集聚合 ----
@pytest.mark.asyncio
async def test_dashboard_aggregates_match_dataset(db_factory) -> None:
    today = date.today()
    await _seed_active_plan(db_factory, today)
    await _seed_practice(db_factory)
    await _seed_report(db_factory)

    async with db_factory() as db:
        service = StudyDashboardService(db, tenant_id=TENANT, user_id=USER)
        dashboard = await service.build_dashboard(today=today)

        assert dashboard["streak"]["current_streak"] == 1
        plan = dashboard["plan"]
        assert plan["active_plan_title"] == "冲刺计划"
        assert plan["tasks_done"] == 1
        assert plan["total_tasks"] == 2
        assert plan["completion_rate"] == 0.5

        todays = dashboard["today"]
        assert todays["tasks_done"] == 1
        assert todays["total_tasks"] == 2
        assert dashboard["study_minutes"]["today_minutes"] >= 30
        assert dashboard["study_minutes"]["week_minutes"] >= 30

        interviews = dashboard["interviews"]
        assert interviews["total_reports"] == 1
        assert interviews["latest_score"] == 72
        assert interviews["average_score"] == 72.0

        practice = dashboard["practice"]
        assert practice["total_attempts"] == 2
        assert practice["correct_rate"] == 0.5
        assert practice["wrong_book_count"] == 1

        weak_tags = {item["tag"] for item in dashboard["weak_points"]}
        assert "RAG 召回" in weak_tags
        assert "行测" in weak_tags

        assert dashboard["advice"]["source"] == "rule"
        assert dashboard["advice"]["text"]


# ---- TR-5.2 LLM 建议失败降级 ----
@pytest.mark.asyncio
async def test_dashboard_llm_advice_failure_falls_back(db_factory) -> None:
    today = date.today()
    await _seed_active_plan(db_factory, today)

    async def boom(snapshot: dict) -> dict:
        raise RuntimeError("llm down")

    async with db_factory() as db:
        service = StudyDashboardService(
            db, tenant_id=TENANT, user_id=USER, advice_provider=boom
        )
        dashboard = await service.build_dashboard(today=today)
        assert dashboard["advice"]["source"] == "rule"
        assert dashboard["advice"]["action"]


@pytest.mark.asyncio
async def test_dashboard_llm_advice_used_when_provided(db_factory) -> None:
    async with db_factory() as db:
        async def fake_provider(snapshot: dict) -> dict:
            return {"text": "今天状态不错，保持节奏。", "action": "继续刷题"}

        service = StudyDashboardService(
            db, tenant_id=TENANT, user_id=USER, advice_provider=fake_provider
        )
        dashboard = await service.build_dashboard(today=date.today())
        assert dashboard["advice"]["source"] == "llm"
        assert dashboard["advice"]["text"] == "今天状态不错，保持节奏。"
        assert dashboard["advice"]["action"] == "继续刷题"


# ---- 冷启动空数据 ----
@pytest.mark.asyncio
async def test_dashboard_empty_state(db_factory) -> None:
    async with db_factory() as db:
        service = StudyDashboardService(db, tenant_id=TENANT, user_id=USER)
        dashboard = await service.build_dashboard(today=date.today())
        assert dashboard["plan"]["active_plan_id"] is None
        assert dashboard["interviews"]["total_reports"] == 0
        assert dashboard["practice"]["total_attempts"] == 0
        assert dashboard["streak"]["current_streak"] == 0
        assert dashboard["advice"]["source"] == "rule"
        assert "模拟面试" in dashboard["advice"]["text"]


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


def test_api_study_dashboard(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="dashboard-api")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "dashboard-e2e@example.com")
        response = client.get("/study/dashboard", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        for key in ("streak", "today", "study_minutes", "interviews", "practice", "plan", "weak_points", "advice"):
            assert key in body
        assert body["advice"]["source"] == "rule"

    import asyncio

    asyncio.run(engine.dispose())
