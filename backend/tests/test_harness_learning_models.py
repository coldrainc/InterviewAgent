"""Task 1 (harness 学习数据底座) 模型与约束测试。

覆盖迁移 20260905_0010 引入的四张新表与字段：
- 新表均带 tenant_id / user_id 隔离列；
- interview_reports / review_checkins / user_achievements 的唯一约束；
- review_plan_tasks 新字段 source / link_type 的默认值。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    InterviewReportModel,
    InterviewSessionModel,
    PracticeAttemptModel,
    PracticeQuestionModel,
    ReviewCheckinModel,
    ReviewDayModel,
    ReviewPlanModel,
    ReviewTaskModel,
    UserAchievementModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url


TENANT = "default"
USER = "anonymous"


def _session_id() -> str:
    return f"test-session-{uuid.uuid4().hex[:8]}"


async def _seed_plan(session) -> uuid.UUID:
    plan = ReviewPlanModel(
        tenant_id=TENANT,
        user_id=USER,
        plan_key=f"plan-{uuid.uuid4().hex[:8]}",
        title="测试计划",
        start_date=date(2026, 9, 1),
    )
    session.add(plan)
    await session.flush()
    day = ReviewDayModel(
        plan_id=plan.id, tenant_id=TENANT, user_id=USER,
        day_key="day-01", sort_order=1, scheduled_date=date(2026, 9, 1),
    )
    session.add(day)
    await session.flush()
    task = ReviewTaskModel(
        plan_id=plan.id, day_id=day.id, tenant_id=TENANT, user_id=USER,
        task_key="task-1", title="任务一", sort_order=1,
    )
    session.add(task)
    await session.flush()
    return plan.id


async def _seed_session(session, plan_task_id: uuid.UUID | None = None) -> uuid.UUID:
    sess = InterviewSessionModel(
        tenant_id=TENANT,
        user_id=USER,
        mode="interviewer",
        industry="互联网",
        candidate_name="张三",
        target_role="AI 应用工程师",
        seniority="3 年",
        plan_task_id=plan_task_id,
    )
    session.add(sess)
    await session.flush()
    return sess.id


async def _seed_question(session) -> uuid.UUID:
    q = PracticeQuestionModel(
        tenant_id=TENANT,
        user_id=USER,
        practice_category="internet",
        prompt="RAG 的召回阶段做什么？",
        answer="召回相关文档片段",
        content_hash=uuid.uuid4().hex,
    )
    session.add(q)
    await session.flush()
    return q.id


@pytest_asyncio.fixture
async def session_factory():
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_new_tables_have_tenant_and_user_columns():
    for model in (InterviewReportModel, PracticeAttemptModel, ReviewCheckinModel, UserAchievementModel):
        columns = model.__table__.c
        assert "tenant_id" in columns
        assert "user_id" in columns


@pytest.mark.asyncio
async def test_review_plan_task_new_field_defaults(session_factory):
    async with session_factory() as session:
        await _seed_plan(session)
        task = (await session.execute(
            ReviewTaskModel.__table__.select().where(ReviewTaskModel.task_key == "task-1")
        )).mappings().one()
        assert task["source"] == "plan"
        assert task["link_type"] == "none"
        assert task["link_payload_json"] == {}
        assert task["source_ref"] is None
        assert task["reason"] is None
        await session.rollback()


@pytest.mark.asyncio
async def test_interview_report_unique_per_session(session_factory):
    async with session_factory() as session:
        sid = await _seed_session(session)
        for _ in range(2):
            session.add(InterviewReportModel(
                tenant_id=TENANT, user_id=USER, session_id=sid,
                mode="interviewer", total_score=80,
            ))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_review_checkin_unique_per_plan_per_day(session_factory):
    async with session_factory() as session:
        plan_id = await _seed_plan(session)
        for _ in range(2):
            session.add(ReviewCheckinModel(
                tenant_id=TENANT, user_id=USER, plan_id=plan_id,
                checkin_date=date(2026, 9, 1), tasks_done=3, total_tasks=5,
            ))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_user_achievement_unique_per_key(session_factory):
    async with session_factory() as session:
        for _ in range(2):
            session.add(UserAchievementModel(
                tenant_id=TENANT, user_id=USER,
                achievement_key="streak-3",
                unlocked_at=datetime.now(timezone.utc),
            ))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_practice_attempt_and_checkin_persist(session_factory):
    async with session_factory() as session:
        qid = await _seed_question(session)
        plan_id = await _seed_plan(session)
        session.add(PracticeAttemptModel(
            tenant_id=TENANT, user_id=USER, question_id=qid,
            answer="召回文档", is_correct=True, score=100, elapsed_seconds=42,
        ))
        session.add(ReviewCheckinModel(
            tenant_id=TENANT, user_id=USER, plan_id=plan_id,
            checkin_date=date(2026, 9, 2), tasks_done=5, total_tasks=5,
            elapsed_minutes=60,
        ))
        session.add(UserAchievementModel(
            tenant_id=TENANT, user_id=USER, achievement_key="first-checkin",
            unlocked_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        attempts = (await session.execute(PracticeAttemptModel.__table__.select())).all()
        checkins = (await session.execute(ReviewCheckinModel.__table__.select())).all()
        achievements = (await session.execute(UserAchievementModel.__table__.select())).all()
        assert len(attempts) == 1
        assert attempts[0].is_correct is True
        assert len(checkins) == 1
        assert checkins[0].tasks_done == 5
        assert len(achievements) == 1
