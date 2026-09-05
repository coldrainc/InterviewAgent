"""Task 7 成就引擎测试。

覆盖：
- TR-7.1 事件序列推进时各成就满足条件恰好解锁（首场面试/报告/streak/刷题/错题清零/计划通关/自我介绍）；
- TR-7.2 重复评估幂等：不产生重复成就记录；
- 未达标成就返回 locked 且带进度；
- GET /study/achievements API 端到端。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    InterviewSessionModel,
    PracticeAttemptModel,
    PracticeQuestionModel,
    PracticeWrongBookModel,
    ReviewCheckinModel,
    ReviewPlanModel,
    UserAchievementModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.repositories.interview_report_repository import InterviewReportRepository
from interview_agent.repositories.review_checkin_repository import ReviewCheckinRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.achievement_service import (
    ACHIEVEMENT_RULES,
    AchievementService,
)

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


async def _add_completed_session(db, *, focus_intro: bool = False) -> uuid.UUID:
    session = InterviewSessionModel(
        tenant_id=TENANT,
        user_id=USER,
        mode="interviewer",
        industry="互联网",
        candidate_name="张三",
        target_role="前端工程师",
        seniority="高级",
        status="completed",
        config_json={"focus_areas": ["自我介绍"]} if focus_intro else {},
    )
    db.add(session)
    await db.flush()
    return session.id


async def _add_report(db, session_id: uuid.UUID) -> None:
    await InterviewReportRepository(db, tenant_id=TENANT, user_id=USER).upsert_report(
        session_id=session_id,
        mode="interviewer",
        total_score=70,
        dimension_scores={"基础": 3},
        per_question=[],
        evidence=[],
        strength_tags=[],
        weakness_tags=["算法"],
        suggestions=["多练"],
        summary_text="尚可",
    )


async def _add_attempts(db, question_id: uuid.UUID, count: int) -> None:
    for _ in range(count):
        db.add(PracticeAttemptModel(
            tenant_id=TENANT,
            user_id=USER,
            question_id=question_id,
            question_type="short_answer",
            answer="我的回答",
            is_correct=True,
            score=80,
            elapsed_seconds=120,
        ))
    await db.flush()


async def _achievement_rows(db) -> int:
    result = await db.execute(
        select(func.count()).select_from(UserAchievementModel).where(
            UserAchievementModel.tenant_id == TENANT,
            UserAchievementModel.user_id == USER,
        )
    )
    return int(result.scalar() or 0)


@pytest.mark.asyncio
async def test_achievement_unlock_sequence(db_factory) -> None:
    async with db_factory() as db:
        svc = AchievementService(db, tenant_id=TENANT, user_id=USER)

        listing = await svc.list_achievements()
        assert listing["unlocked_count"] == 0
        assert listing["total_count"] == len(ACHIEVEMENT_RULES)
        assert all(item["unlocked"] is False for item in listing["achievements"])

        # 首场面试（无报告 → first_report 未解锁）
        session_id = await _add_completed_session(db)
        unlocked = await svc.evaluate()
        assert "first_interview" in unlocked
        assert "first_report" not in unlocked

        # 首份报告
        await _add_report(db, session_id)
        unlocked = await svc.evaluate()
        assert "first_report" in unlocked

        # 连续 7 天打卡
        plan = ReviewPlanModel(
            tenant_id=TENANT, user_id=USER, plan_key=f"plan-{uuid.uuid4().hex[:6]}",
            title="打卡计划", status="active",
        )
        db.add(plan)
        await db.flush()
        checkin_repo = ReviewCheckinRepository(db, tenant_id=TENANT, user_id=USER)
        start = date(2026, 9, 1)
        for offset in range(7):
            await checkin_repo.upsert_checkin(
                plan.id, start + timedelta(days=offset),
                tasks_done=1, total_tasks=2, elapsed_minutes=30, note="",
            )
        unlocked = await svc.evaluate()
        assert "streak_7" in unlocked
        assert "streak_30" not in unlocked

        # 49 道作答 → 未达标，进度 49
        question = PracticeQuestionModel(
            tenant_id=TENANT, user_id=USER, practice_category="internet",
            prompt="题目", content_hash=uuid.uuid4().hex,
        )
        db.add(question)
        await db.flush()
        await _add_attempts(db, question.id, 49)
        unlocked = await svc.evaluate()
        assert "practice_50" not in unlocked
        listing = await svc.list_achievements()
        p50 = next(item for item in listing["achievements"] if item["key"] == "practice_50")
        assert p50["unlocked"] is False and p50["progress"] == 49

        # 再答 1 道 → 50 解锁
        await _add_attempts(db, question.id, 1)
        unlocked = await svc.evaluate()
        assert "practice_50" in unlocked
        assert "practice_100" not in unlocked

        # 100 道
        await _add_attempts(db, question.id, 50)
        unlocked = await svc.evaluate()
        assert "practice_100" in unlocked

        # 错题清零：有过错题且全部 mastered
        db.add(PracticeWrongBookModel(
            tenant_id=TENANT, user_id=USER, question_id=question.id,
            mark_type="mastered", mastery_level=5, attempt_count=3, correct_count=3,
        ))
        await db.flush()
        unlocked = await svc.evaluate()
        assert "wrong_book_clear" in unlocked

        # 计划通关：2/2 任务完成
        site_repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        plan2 = await site_repo.create_plan(
            plan_data={"plan_key": f"p2-{uuid.uuid4().hex[:6]}", "title": "通关计划", "status": "active"},
            phases=[{"id": "p1", "title": "阶段", "goal": "完成"}],
            days=[{"id": "day-1", "day": "Day 1", "phase": "p1", "title": "唯一一天"}],
            tasks_per_day={"day-1": [
                {"id": "t1", "title": "任务一"},
                {"id": "t2", "title": "任务二"},
            ]},
            intro_scripts=[],
            star_cards=[],
            a4_memory=[],
        )
        days = await site_repo.list_days(plan2.id)
        for task in days[0].tasks:
            await site_repo.update_progress(task.id, {"done": True})
        unlocked = await svc.evaluate()
        assert "plan_completed" in unlocked

        # 自我介绍专项 10 次
        intro_question = PracticeQuestionModel(
            tenant_id=TENANT, user_id=USER, practice_category="civil-service",
            prompt="请做自我介绍", question_type="自我介绍", content_hash=uuid.uuid4().hex,
        )
        db.add(intro_question)
        await db.flush()
        await _add_attempts(db, intro_question.id, 10)
        unlocked = await svc.evaluate()
        assert "intro_10" in unlocked

        # 30 天 streak 放最后补齐
        for offset in range(7, 30):
            await checkin_repo.upsert_checkin(
                plan.id, start + timedelta(days=offset),
                tasks_done=1, total_tasks=2, elapsed_minutes=20, note="",
            )
        unlocked = await svc.evaluate()
        assert "streak_30" in unlocked

        listing = await svc.list_achievements()
        assert listing["unlocked_count"] == len(ACHIEVEMENT_RULES)
        assert all(item["unlocked"] for item in listing["achievements"])


@pytest.mark.asyncio
async def test_achievement_evaluation_is_idempotent(db_factory) -> None:
    async with db_factory() as db:
        await _add_completed_session(db)
        svc = AchievementService(db, tenant_id=TENANT, user_id=USER)

        first = await svc.evaluate()
        assert "first_interview" in first
        rows_after_first = await _achievement_rows(db)
        assert rows_after_first == 1

        # 重复评估不再解锁、不产生重复行
        second = await svc.evaluate()
        third = await svc.evaluate()
        assert second == []
        assert third == []
        assert await _achievement_rows(db) == 1

        # 已解锁成就带解锁时间
        listing = await svc.list_achievements()
        item = next(a for a in listing["achievements"] if a["key"] == "first_interview")
        assert item["unlocked"] is True
        assert item["unlocked_at"] is not None


@pytest.mark.asyncio
async def test_wrong_book_clear_requires_history(db_factory) -> None:
    """从未有过错题时不解锁错题清零。"""
    async with db_factory() as db:
        svc = AchievementService(db, tenant_id=TENANT, user_id=USER)
        await svc.evaluate()
        listing = await svc.list_achievements()
        item = next(a for a in listing["achievements"] if a["key"] == "wrong_book_clear")
        assert item["unlocked"] is False


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


def test_api_achievements_endpoint(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="achievement-api")
    app = create_app(object_storage=storage, database_engine=engine)
    with TestClient(app) as client:
        headers = _register_headers(client, "achievement@example.com")
        resp = client.get("/study/achievements", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == len(ACHIEVEMENT_RULES)
        assert body["unlocked_count"] == 0
        keys = {item["key"] for item in body["achievements"]}
        assert {
            "first_interview", "first_report", "streak_7", "streak_30",
            "practice_50", "practice_100", "wrong_book_clear",
            "plan_completed", "intro_10",
        } <= keys
        assert "metrics" in body
