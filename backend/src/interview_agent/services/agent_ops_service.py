from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from interview_agent.infrastructure.db.models import AgentSpanModel, AgentTraceModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentOpsService:
    def __init__(self, session: AsyncSession, tenant_id: str = "default", user_id: str = "anonymous") -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def create_trace(
        self,
        *,
        trace_type: str,
        title: str,
        job_id: str | None = None,
        session_id: str | None = None,
        input_payload: dict | None = None,
    ) -> AgentTraceModel:
        trace = AgentTraceModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            job_id=uuid.UUID(job_id) if job_id else None,
            session_id=session_id,
            trace_type=trace_type,
            title=title,
            status="running",
            input_json=input_payload or {},
            result_json={},
            metrics_json={},
            created_at=_now(),
        )
        self.session.add(trace)
        await self.session.flush()
        return trace

    async def finish_trace(
        self,
        trace_id: str | uuid.UUID,
        *,
        status: str = "succeeded",
        result_payload: dict | None = None,
        metrics: dict | None = None,
    ) -> AgentTraceModel | None:
        trace = await self.session.get(AgentTraceModel, _uuid(trace_id))
        if trace is None or trace.tenant_id != self.tenant_id or trace.user_id != self.user_id:
            return None
        trace.status = status
        trace.result_json = result_payload or trace.result_json
        trace.metrics_json = metrics or trace.metrics_json
        trace.finished_at = _now()
        await self.session.flush()
        return trace

    async def add_span(
        self,
        trace_id: str | uuid.UUID,
        *,
        name: str,
        span_type: str = "step",
        status: str = "succeeded",
        input_payload: dict | None = None,
        output_payload: dict | None = None,
        metrics: dict | None = None,
        error_message: str | None = None,
    ) -> AgentSpanModel:
        timestamp = _now()
        span = AgentSpanModel(
            trace_id=_uuid(trace_id),
            name=name,
            span_type=span_type,
            status=status,
            input_json=input_payload or {},
            output_json=output_payload or {},
            metrics_json=metrics or {},
            error_message=error_message,
            started_at=timestamp,
            finished_at=timestamp if status in {"succeeded", "failed", "skipped"} else None,
        )
        self.session.add(span)
        await self.session.flush()
        return span

    async def list_traces(self, *, limit: int = 50) -> list[AgentTraceModel]:
        result = await self.session.execute(
            select(AgentTraceModel)
            .where(AgentTraceModel.tenant_id == self.tenant_id, AgentTraceModel.user_id == self.user_id)
            .order_by(AgentTraceModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_trace(self, trace_id: str | uuid.UUID) -> AgentTraceModel | None:
        result = await self.session.execute(
            select(AgentTraceModel)
            .options(selectinload(AgentTraceModel.spans))
            .where(
                AgentTraceModel.id == _uuid(trace_id),
                AgentTraceModel.tenant_id == self.tenant_id,
                AgentTraceModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def metrics_summary(self) -> dict:
        result = await self.session.execute(
            select(AgentTraceModel.status, func.count(AgentTraceModel.id))
            .where(AgentTraceModel.tenant_id == self.tenant_id, AgentTraceModel.user_id == self.user_id)
            .group_by(AgentTraceModel.status)
        )
        trace_counts = {status: count for status, count in result.all()}
        span_count = await self.session.scalar(
            select(func.count(AgentSpanModel.id))
            .join(AgentTraceModel, AgentTraceModel.id == AgentSpanModel.trace_id)
            .where(AgentTraceModel.tenant_id == self.tenant_id, AgentTraceModel.user_id == self.user_id)
        )
        return {
            "trace_counts": trace_counts,
            "span_count": int(span_count or 0),
        }


def trace_to_dict(trace: AgentTraceModel, *, include_spans: bool = False) -> dict:
    payload = {
        "id": str(trace.id),
        "tenant_id": trace.tenant_id,
        "user_id": trace.user_id,
        "job_id": str(trace.job_id) if trace.job_id else None,
        "session_id": trace.session_id,
        "trace_type": trace.trace_type,
        "title": trace.title,
        "status": trace.status,
        "input": trace.input_json,
        "result": trace.result_json,
        "metrics": trace.metrics_json,
        "created_at": trace.created_at.isoformat(),
        "finished_at": trace.finished_at.isoformat() if trace.finished_at else None,
    }
    if include_spans:
        payload["spans"] = [span_to_dict(span) for span in sorted(trace.spans, key=lambda item: item.started_at)]
    return payload


def span_to_dict(span: AgentSpanModel) -> dict:
    return {
        "id": str(span.id),
        "trace_id": str(span.trace_id),
        "parent_span_id": span.parent_span_id,
        "name": span.name,
        "span_type": span.span_type,
        "status": span.status,
        "input": span.input_json,
        "output": span.output_json,
        "metrics": span.metrics_json,
        "error_message": span.error_message,
        "started_at": span.started_at.isoformat(),
        "finished_at": span.finished_at.isoformat() if span.finished_at else None,
    }


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
