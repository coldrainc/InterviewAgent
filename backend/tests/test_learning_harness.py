from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    InterviewReportModel,
    InterviewSessionModel,
    ReviewDayModel,
    ReviewPlanModel,
    ReviewTaskModel,
)
from interview_agent.learning.errors import VersionConflictError
from interview_agent.learning.models import LearningEffectReceiptModel, LearningTaskRunModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.learning.service import LearningHarnessService
from interview_agent.repositories.review_site_repository import ReviewSiteRepository

TENANT = "default"
USER = "learner"


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


async def _seed_task(
    factory, *, link_type: str = "none", link_payload: dict | None = None
) -> uuid.UUID:
    async with factory() as db:
        plan = ReviewPlanModel(
            tenant_id=TENANT,
            user_id=USER,
            plan_key=f"learning-{uuid.uuid4().hex[:8]}",
            title="Learning Harness plan",
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
        task = ReviewTaskModel(
            plan_id=plan.id,
            day_id=day.id,
            tenant_id=TENANT,
            user_id=USER,
            task_key="task-1",
            title="Complete one learning task",
            link_type=link_type,
            link_payload_json=link_payload or {},
            simulation=link_type == "interview",
        )
        db.add(task)
        await db.commit()
        return task.id


@pytest.mark.asyncio
async def test_task_projection_has_owner_scoped_navigation_target(db_factory) -> None:
    task_id = await _seed_task(
        db_factory,
        link_type="practice",
        link_payload={"category": "leetcode", "plan_id": "untrusted"},
    )
    async with db_factory() as db:
        task = await LearningHarnessService(
            db, tenant_id=TENANT, user_id=USER
        ).task_view(str(task_id))

        assert task["link_payload"]["task_id"] == str(task_id)
        assert task["link_payload"]["plan_id"] != "untrusted"
        assert task["link_payload"]["day_id"]
        assert task["link_payload"]["category"] == "leetcode"


@pytest.mark.asyncio
async def test_manual_task_records_start_complete_and_reopen_receipts(db_factory) -> None:
    task_id = await _seed_task(db_factory)
    async with db_factory() as db:
        service = LearningHarnessService(db, tenant_id=TENANT, user_id=USER)

        started = await service.execute(str(task_id), action="start")
        assert started["task"]["status"] == "in_progress"
        assert started["receipt"]["previous_status"] == "todo"

        completed = await service.execute(
            str(task_id),
            action="complete",
            elapsed_minutes=20,
            mastery_score=4,
            evidence={"note": "reviewed and summarized"},
        )
        assert completed["receipt"]["accepted"] is True
        assert completed["task"]["status"] == "completed"
        assert completed["task"]["verification"]["mode"] == "self_attested"

        reopened = await service.execute(str(task_id), action="reopen")
        assert reopened["task"]["status"] == "todo"
        assert reopened["task"]["done"] is False
        progress = await ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER).get_or_create_progress(task_id)
        receipts = progress.metadata_json["learning_harness"]["receipts"]
        assert [item["action"] for item in receipts] == ["start", "complete", "reopen"]


@pytest.mark.asyncio
async def test_interview_task_requires_completed_linked_report(db_factory) -> None:
    task_id = await _seed_task(db_factory, link_type="interview")
    async with db_factory() as db:
        service = LearningHarnessService(db, tenant_id=TENANT, user_id=USER)
        rejected = await service.execute(str(task_id), action="complete")
        assert rejected["receipt"]["accepted"] is False
        assert rejected["task"]["status"] == "blocked"
        assert rejected["task"]["done"] is False

        session = InterviewSessionModel(
            id=uuid.uuid4(),
            tenant_id=TENANT,
            user_id=USER,
            mode="interviewer",
            industry="internet",
            candidate_name="Candidate",
            target_role="AI Engineer",
            seniority="senior",
            config_json={},
            state_json={},
            status="completed",
            plan_task_id=task_id,
        )
        db.add(session)
        await db.flush()
        db.add(
            InterviewReportModel(
                tenant_id=TENANT,
                user_id=USER,
                session_id=session.id,
                mode="interviewer",
                total_score=80,
            )
        )
        await db.flush()

        verified = await service.execute(str(task_id), action="verify")
        assert verified["receipt"]["accepted"] is True
        assert verified["task"]["status"] == "completed"
        assert verified["task"]["verification"]["mode"] == "automatic"
        assert verified["task"]["verification"]["evidence"]["session_id"] == str(session.id)


@pytest.mark.asyncio
async def test_command_is_idempotent_and_persists_formal_receipt(db_factory) -> None:
    task_id = await _seed_task(db_factory)
    async with db_factory() as db:
        service = LearningHarnessService(db, tenant_id=TENANT, user_id=USER)
        first = await service.execute(
            str(task_id), action="start", idempotency_key="start-once", expected_version=0
        )
        replay = await service.execute(
            str(task_id), action="start", idempotency_key="start-once", expected_version=0
        )
        assert replay["idempotent_replay"] is True
        assert replay["receipt"]["receipt_id"] == first["receipt"]["receipt_id"]

        receipts = list((await db.execute(select(LearningEffectReceiptModel))).scalars())
        runs = list((await db.execute(select(LearningTaskRunModel))).scalars())
        assert len(receipts) == 1
        assert len(runs) == 1
        assert runs[0].version == 1


@pytest.mark.asyncio
async def test_stale_expected_version_is_rejected(db_factory) -> None:
    task_id = await _seed_task(db_factory)
    async with db_factory() as db:
        service = LearningHarnessService(db, tenant_id=TENANT, user_id=USER)
        await service.execute(str(task_id), action="start", expected_version=0)
        with pytest.raises(VersionConflictError) as conflict:
            await service.execute(str(task_id), action="reopen", expected_version=0)
        assert conflict.value.current == 1


def test_learning_task_command_api_round_trip() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from interview_agent.infrastructure.db.session import configure_database_for_tests
    from interview_agent.infrastructure.security import RequestContext, request_context
    from interview_agent.learning.routes import create_learning_router

    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare() -> uuid.UUID:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return await _seed_task(factory)

    task_id = asyncio.run(prepare())
    configure_database_for_tests(engine)
    app = FastAPI()
    app.include_router(create_learning_router())
    app.dependency_overrides[request_context] = lambda: RequestContext(
        tenant_id=TENANT,
        user_id=USER,
        authenticated=False,
    )

    with TestClient(app) as client:
        unauthorized = client.get(f"/learning/tasks/{task_id}")
        assert unauthorized.status_code == 401

    app.dependency_overrides[request_context] = lambda: RequestContext(
        tenant_id=TENANT,
        user_id=USER,
        authenticated=True,
    )

    with TestClient(app) as client:
        started = client.post(
            f"/learning/tasks/{task_id}/commands",
            headers={"Idempotency-Key": "api-start"},
            json={"action": "start", "expected_version": 0},
        )
        assert started.status_code == 200, started.text
        assert started.json()["task"]["status"] == "in_progress"

        conflict = client.post(
            f"/learning/tasks/{task_id}/commands",
            headers={"Idempotency-Key": "api-stale"},
            json={"action": "reopen", "expected_version": 0},
        )
        assert conflict.status_code == 409
        conflict_detail = conflict.json()["detail"]
        assert conflict_detail["expected_version"] == 0
        assert conflict_detail["current_version"] == 1
        assert conflict_detail["current_task"]["status"] == "in_progress"
        assert conflict_detail["resolution"] == "refresh_and_retry"

        completed = client.post(
            f"/learning/tasks/{task_id}/commands",
            headers={"Idempotency-Key": "api-complete"},
            json={"action": "complete", "expected_version": 1, "elapsed_minutes": 15, "evidence": {"note": "done"}},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["receipt"]["accepted"] is True

        fetched = client.get(f"/learning/tasks/{task_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["status"] == "completed"
        assert fetched.json()["elapsed_minutes"] == 15

    asyncio.run(engine.dispose())
