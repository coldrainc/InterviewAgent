from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import AgentSpanModel, Base, JobEventModel, JobStepModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.repositories.job_repository import JobRepository
from interview_agent.services.agent_ops_service import AgentOpsService


@pytest.mark.asyncio
async def test_child_records_cannot_cross_owner_boundary() -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        owner_jobs = JobRepository(session, tenant_id="tenant-a", user_id="user-a")
        job = await owner_jobs.create_job(job_type="workflow", title="private job")
        trace = await AgentOpsService(session, "tenant-a", "user-a").create_trace(
            trace_type="workflow",
            title="private trace",
            job_id=str(job.id),
        )
        await session.commit()

        attacker_jobs = JobRepository(session, tenant_id="tenant-a", user_id="user-b")
        with pytest.raises(LookupError):
            await attacker_jobs.upsert_step(
                job.id,
                step_key="injected",
                title="injected",
                status="succeeded",
            )
        with pytest.raises(LookupError):
            await attacker_jobs.add_event(job.id, "injected", "injected")
        assert await attacker_jobs.list_events(job.id) == []

        with pytest.raises(LookupError):
            await AgentOpsService(session, "tenant-a", "user-b").add_span(
                trace.id,
                name="injected",
            )
        with pytest.raises(LookupError):
            await AgentOpsService(session, "tenant-a", "user-b").create_trace(
                trace_type="workflow",
                title="injected",
                job_id=str(job.id),
            )

        assert await session.scalar(select(func.count(JobStepModel.id))) == 0
        assert await session.scalar(select(func.count(JobEventModel.id))) == 1
        assert await session.scalar(select(func.count(AgentSpanModel.id))) == 0

    await engine.dispose()
