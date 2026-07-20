from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from interview_agent.infrastructure.db.models import JobEventModel, JobModel, JobStepModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class JobRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default", user_id: str = "anonymous") -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def create_job(self, *, job_type: str, title: str, input_payload: dict | None = None) -> JobModel:
        job = JobModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            job_type=job_type,
            title=title,
            status="pending",
            input_json=input_payload or {},
            result_json={},
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        self.session.add(job)
        await self.session.flush()
        await self.add_event(job.id, "job.created", f"任务已创建：{title}", {"job_type": job_type})
        return job

    async def get_job(self, job_id: str | uuid.UUID, *, with_children: bool = False) -> JobModel | None:
        parsed = _uuid(job_id)
        if with_children:
            result = await self.session.execute(
                select(JobModel)
                .options(selectinload(JobModel.steps), selectinload(JobModel.events))
                .where(
                    JobModel.id == parsed,
                    JobModel.tenant_id == self.tenant_id,
                    JobModel.user_id == self.user_id,
                )
            )
            return result.scalar_one_or_none()
        model = await self.session.get(JobModel, parsed)
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            return None
        return model

    async def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[JobModel]:
        query = select(JobModel).where(JobModel.tenant_id == self.tenant_id, JobModel.user_id == self.user_id)
        if status:
            query = query.where(JobModel.status == status)
        result = await self.session.execute(query.order_by(JobModel.updated_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def set_job_status(
        self,
        job_id: str | uuid.UUID,
        status: str,
        *,
        result_payload: dict | None = None,
        error_message: str | None = None,
    ) -> JobModel | None:
        job = await self.get_job(job_id)
        if not job:
            return None
        timestamp = now_utc()
        job.status = status
        job.updated_at = timestamp
        if status == "running" and not job.started_at:
            job.started_at = timestamp
        if status in {"succeeded", "failed", "canceled"}:
            job.finished_at = timestamp
        if result_payload is not None:
            job.result_json = result_payload
        if error_message:
            job.error_message = error_message
        await self.session.flush()
        await self.add_event(
            job.id,
            f"job.{status}",
            _status_message(status, job.title),
            {"status": status, "error": error_message or ""},
        )
        return job

    async def upsert_step(
        self,
        job_id: str | uuid.UUID,
        *,
        step_key: str,
        title: str,
        status: str,
        input_payload: dict | None = None,
        output_payload: dict | None = None,
        error_message: str | None = None,
    ) -> JobStepModel:
        parsed_job_id = _uuid(job_id)
        result = await self.session.execute(
            select(JobStepModel).where(JobStepModel.job_id == parsed_job_id, JobStepModel.step_key == step_key)
        )
        step = result.scalar_one_or_none()
        timestamp = now_utc()
        if step is None:
            step = JobStepModel(
                job_id=parsed_job_id,
                step_key=step_key,
                title=title,
                status=status,
                input_json=input_payload or {},
                output_json=output_payload or {},
                created_at=timestamp,
            )
            self.session.add(step)
        else:
            step.title = title
            step.status = status
            if input_payload is not None:
                step.input_json = input_payload
            if output_payload is not None:
                step.output_json = output_payload
        if status == "running" and not step.started_at:
            step.started_at = timestamp
        if status in {"succeeded", "failed", "skipped", "canceled"}:
            step.finished_at = timestamp
        if error_message:
            step.error_message = error_message
        await self.session.flush()
        await self.add_event(
            parsed_job_id,
            f"step.{status}",
            f"{title}：{_short_status(status)}",
            {"step_key": step_key, "status": status, "error": error_message or ""},
        )
        return step

    async def add_event(
        self,
        job_id: str | uuid.UUID,
        event_type: str,
        message: str,
        payload: dict | None = None,
    ) -> JobEventModel:
        event = JobEventModel(
            job_id=_uuid(job_id),
            event_type=event_type,
            message=message,
            payload_json=payload or {},
            created_at=now_utc(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(self, job_id: str | uuid.UUID, *, after_id: str | None = None, limit: int = 100) -> list[JobEventModel]:
        query = select(JobEventModel).where(JobEventModel.job_id == _uuid(job_id))
        if after_id:
            query = query.where(JobEventModel.id != _uuid(after_id))
        result = await self.session.execute(query.order_by(JobEventModel.created_at.asc()).limit(limit))
        events = list(result.scalars().all())
        if after_id:
            seen = True
            filtered: list[JobEventModel] = []
            for event in events:
                if seen:
                    filtered.append(event)
            return filtered
        return events

    async def count_jobs_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(JobModel.status, func.count(JobModel.id))
            .where(JobModel.tenant_id == self.tenant_id, JobModel.user_id == self.user_id)
            .group_by(JobModel.status)
        )
        return {status: count for status, count in result.all()}


def job_to_dict(job: JobModel, *, include_children: bool = False) -> dict:
    payload = {
        "id": str(job.id),
        "tenant_id": job.tenant_id,
        "user_id": job.user_id,
        "job_type": job.job_type,
        "title": job.title,
        "status": job.status,
        "input": job.input_json,
        "result": job.result_json,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    if include_children:
        payload["steps"] = [step_to_dict(step) for step in sorted(job.steps, key=lambda item: item.created_at)]
        payload["events"] = [event_to_dict(event) for event in sorted(job.events, key=lambda item: item.created_at)]
    return payload


def step_to_dict(step: JobStepModel) -> dict:
    return {
        "id": str(step.id),
        "job_id": str(step.job_id),
        "step_key": step.step_key,
        "title": step.title,
        "status": step.status,
        "input": step.input_json,
        "output": step.output_json,
        "error_message": step.error_message,
        "created_at": step.created_at.isoformat(),
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "finished_at": step.finished_at.isoformat() if step.finished_at else None,
    }


def event_to_dict(event: JobEventModel) -> dict:
    return {
        "id": str(event.id),
        "job_id": str(event.job_id),
        "event_type": event.event_type,
        "message": event.message,
        "payload": event.payload_json,
        "created_at": event.created_at.isoformat(),
    }


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _status_message(status: str, title: str) -> str:
    messages = {
        "running": f"任务开始执行：{title}",
        "succeeded": f"任务执行完成：{title}",
        "failed": f"任务执行失败：{title}",
        "canceled": f"任务已取消：{title}",
    }
    return messages.get(status, f"任务状态变更：{status}")


def _short_status(status: str) -> str:
    return {
        "pending": "等待中",
        "running": "执行中",
        "succeeded": "完成",
        "failed": "失败",
        "skipped": "跳过",
        "canceled": "取消",
    }.get(status, status)
