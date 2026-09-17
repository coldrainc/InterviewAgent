from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import Base, ReviewDayModel, ReviewPlanModel, ReviewTaskModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.learning.ability_service import AbilitySnapshotService
from interview_agent.learning.goal_service import GoalService
from interview_agent.learning.revision_service import RevisionService
from interview_agent.repositories.review_site_repository import ReviewSiteRepository

TENANT = "default"
USER = "adaptive-user"


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


async def _seed_overloaded_plan(factory):
    async with factory() as db:
        plan = ReviewPlanModel(
            tenant_id=TENANT,
            user_id=USER,
            plan_key="adaptive-plan",
            title="Adaptive plan",
            status="active",
            start_date=date.today(),
        )
        db.add(plan)
        await db.flush()
        day = ReviewDayModel(
            plan_id=plan.id,
            tenant_id=TENANT,
            user_id=USER,
            day_key="day-1",
            day_label="Day 1",
            scheduled_date=date.today(),
        )
        db.add(day)
        await db.flush()
        unlocked = ReviewTaskModel(
            plan_id=plan.id,
            day_id=day.id,
            tenant_id=TENANT,
            user_id=USER,
            task_key="task-open",
            title="Long unlocked task",
            link_payload_json={"estimated_minutes": 40},
            sort_order=2,
        )
        locked = ReviewTaskModel(
            plan_id=plan.id,
            day_id=day.id,
            tenant_id=TENANT,
            user_id=USER,
            task_key="task-locked",
            title="Locked task",
            link_payload_json={"estimated_minutes": 40, "locked": True},
            sort_order=1,
        )
        db.add_all([unlocked, locked])
        await db.commit()
        return plan.id, unlocked.id, locked.id


@pytest.mark.asyncio
async def test_goal_contract_versions_and_snapshot_preserves_unknown_dimensions(db_factory) -> None:
    async with db_factory() as db:
        goals = GoalService(db, tenant_id=TENANT, user_id=USER)
        created = await goals.upsert({
            "title": "Backend interview",
            "target_role": "Senior Engineer",
            "daily_minutes": 45,
            "success_criteria": {"interview_score": 80},
        })
        assert created["version"] == 1
        updated = await goals.upsert({
            "title": "Backend interview",
            "target_role": "Staff Engineer",
            "daily_minutes": 60,
            "expected_version": 1,
        })
        assert updated["version"] == 2

        snapshot = await AbilitySnapshotService(db, tenant_id=TENANT, user_id=USER).compute(
            goal_id=uuid.UUID(created["id"])
        )
        assert snapshot["dimensions"] == {}
        assert snapshot["confidence"] == 0


@pytest.mark.asyncio
async def test_revision_defers_only_unlocked_tasks_and_can_revert(db_factory) -> None:
    plan_id, unlocked_id, locked_id = await _seed_overloaded_plan(db_factory)
    async with db_factory() as db:
        service = RevisionService(db, tenant_id=TENANT, user_id=USER)
        revision = await service.propose(str(plan_id), daily_minutes=20, dimensions={})
        assert revision is not None
        assert str(unlocked_id) in revision["diff"]["defer_task_ids"]
        assert str(locked_id) not in revision["diff"]["defer_task_ids"]

        applied = await service.decide(revision["id"], "apply")
        assert applied["status"] == "applied"
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        assert (await repo.get_task(unlocked_id)).link_payload_json["deferred"] is True
        assert (await repo.get_task(locked_id)).link_payload_json.get("deferred") is not True

        reverted = await service.decide(revision["id"], "revert")
        assert reverted["status"] == "reverted"
        assert (await repo.get_task(unlocked_id)).link_payload_json["deferred"] is False
