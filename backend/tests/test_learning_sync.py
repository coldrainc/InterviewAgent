from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import Base, ReviewDayModel, ReviewPlanModel, ReviewTaskModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.learning.command_service import LearningCommandService
from interview_agent.learning.sync_service import LearningSyncService


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


async def _seed_task(db) -> str:
    plan = ReviewPlanModel(
        tenant_id="default",
        user_id="sync-user",
        plan_key=f"sync-{uuid.uuid4()}",
        title="Sync plan",
        status="active",
        start_date=date.today(),
    )
    db.add(plan)
    await db.flush()
    day = ReviewDayModel(
        plan_id=plan.id,
        tenant_id="default",
        user_id="sync-user",
        day_key="today",
        day_label="Today",
        scheduled_date=date.today(),
    )
    db.add(day)
    await db.flush()
    task = ReviewTaskModel(
        plan_id=plan.id,
        day_id=day.id,
        tenant_id="default",
        user_id="sync-user",
        task_key="sync-task",
        title="Sync task",
    )
    db.add(task)
    await db.flush()
    return str(task.id)


@pytest.mark.asyncio
async def test_sync_cursor_pages_immutable_receipts_and_isolates_users(db_factory) -> None:
    async with db_factory() as db:
        task_id = await _seed_task(db)
        commands = LearningCommandService(db, tenant_id="default", user_id="sync-user")
        await commands.execute(task_id, action="start", idempotency_key="sync-start", expected_version=0)
        await commands.execute(task_id, action="reopen", idempotency_key="sync-reopen", expected_version=1)

        sync = LearningSyncService(db, tenant_id="default", user_id="sync-user")
        first = await sync.pull(cursor=None, limit=1)
        assert first["authority"] == "server"
        assert first["has_more"] is True
        assert first["events"][0]["version"] == 1
        second = await sync.pull(cursor=first["next_cursor"], limit=10)
        assert [item["version"] for item in second["events"]] == [2]
        assert second["has_more"] is False

        isolated = await LearningSyncService(
            db, tenant_id="default", user_id="another-user"
        ).pull(cursor=None)
        assert isolated["events"] == []

        with pytest.raises(ValueError, match="invalid sync cursor"):
            await sync.pull(cursor="not-a-cursor")
