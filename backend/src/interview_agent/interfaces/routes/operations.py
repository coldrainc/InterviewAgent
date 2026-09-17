from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from starlette.responses import StreamingResponse

from interview_agent.infrastructure.db.models import EvalRunModel
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.schemas import EvalRunCreateRequest, JobCreateRequest, WorkflowRunRequest
from interview_agent.learning.observability import learning_command_metrics
from interview_agent.repositories.job_repository import JobRepository, event_to_dict, job_to_dict
from interview_agent.services.agent_ops_service import AgentOpsService, trace_to_dict
from interview_agent.services.workflow_runner import TERMINAL_JOB_STATUSES, create_and_start_job


def create_operations_router() -> APIRouter:
    router = APIRouter()

    @router.post("/jobs")
    async def create_job(
        request: JobCreateRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        return await create_and_start_job(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            job_type=request.job_type,
            title=request.title or _default_job_title(request.job_type),
            input_payload=request.input,
        )

    @router.get("/jobs")
    async def list_jobs(
        status: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        async with session_scope() as db:
            jobs = await JobRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_jobs(status=status, limit=limit, offset=offset)
        return [job_to_dict(job) for job in jobs]

    @router.get("/jobs/{job_id}")
    async def get_job(
        job_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            job = await JobRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get_job(job_id, with_children=True)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job_to_dict(job, include_children=True)

    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            repo = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await repo.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="job not found")
            if job.status not in TERMINAL_JOB_STATUSES:
                job = await repo.set_job_status(job.id, "canceled")
        return job_to_dict(job) if job else {"id": job_id, "status": "canceled"}

    @router.get("/jobs/{job_id}/events/stream")
    async def stream_job_events(
        job_id: str,
        http_request: Request,
        context: RequestContext = Depends(request_context),
    ) -> StreamingResponse:
        _require_authenticated(context)

        async def event_stream():
            seen: set[str] = set()
            for _ in range(600):
                async with session_scope() as db:
                    repo = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
                    job = await repo.get_job(job_id)
                    if not job:
                        yield _sse("job.error", {"message": "job not found"})
                        return
                    events = await repo.list_events(job_id, limit=100)
                    terminal = job.status in TERMINAL_JOB_STATUSES
                for event in events:
                    event_id = str(event.id)
                    if event_id in seen:
                        continue
                    seen.add(event_id)
                    yield _sse("job.event", event_to_dict(event))
                if terminal:
                    yield _sse("job.done", {"job_id": job_id, "status": job.status})
                    return
                if await http_request.is_disconnected():
                    return
                await asyncio.sleep(1)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/workflows/run")
    async def run_workflow(
        request: WorkflowRunRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        job_type = "multi_agent" if request.workflow_type == "multi_agent" else "workflow"
        return await create_and_start_job(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            job_type=job_type,
            title=request.title or _default_job_title(job_type),
            input_payload=request.input,
        )

    @router.post("/eval-runs")
    async def create_eval_run(
        request: EvalRunCreateRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        return await create_and_start_job(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            job_type="evaluation",
            title=request.name or "AI 工程能力质量评估",
            input_payload={"cases": request.cases, "metadata": request.metadata, **request.metadata},
        )

    @router.get("/eval-runs")
    async def list_eval_runs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        async with session_scope() as db:
            result = await db.execute(
                select(EvalRunModel)
                .where(EvalRunModel.tenant_id == context.tenant_id, EvalRunModel.user_id == context.user_id)
                .order_by(EvalRunModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            runs = result.scalars().all()
        return [_eval_run_to_dict(run) for run in runs]

    @router.get("/ops/traces")
    async def list_agent_traces(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        async with session_scope() as db:
            traces = await AgentOpsService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_traces(limit=limit, offset=offset)
        return [trace_to_dict(trace) for trace in traces]

    @router.get("/ops/traces/{trace_id}")
    async def get_agent_trace(
        trace_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            trace = await AgentOpsService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace_to_dict(trace, include_spans=True)

    @router.get("/ops/metrics")
    async def ops_metrics(
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            job_counts = await JobRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).count_jobs_by_status()
            trace_metrics = await AgentOpsService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).metrics_summary()
        return {
            "job_counts": job_counts,
            "learning": learning_command_metrics.snapshot(),
            **trace_metrics,
        }

    return router


def _require_authenticated(context: RequestContext) -> None:
    if not context.authenticated or context.user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="请先登录后再继续。",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _default_job_title(job_type: str) -> str:
    return {
        "workflow": "复杂任务编排演示",
        "evaluation": "AI 工程能力质量评估",
        "multi_agent": "多 Agent 协作演示",
    }.get(job_type, "后台任务")


def _eval_run_to_dict(run: EvalRunModel) -> dict:
    return {
        "id": str(run.id),
        "tenant_id": run.tenant_id,
        "user_id": run.user_id,
        "dataset_id": str(run.dataset_id) if run.dataset_id else None,
        "job_id": str(run.job_id) if run.job_id else None,
        "name": run.name,
        "status": run.status,
        "metrics": run.metrics_json,
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
