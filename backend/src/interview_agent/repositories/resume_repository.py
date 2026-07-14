from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.resume import StoredResume
from interview_agent.infrastructure.db.models import ResumeModel


class ResumeRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default", user_id: str = "anonymous") -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def get_by_id(self, resume_id: str) -> StoredResume | None:
        model = await self.session.get(ResumeModel, uuid.UUID(resume_id))
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            return None
        return _to_domain(model)

    async def get_by_content_hash(self, content_hash: str) -> StoredResume | None:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.tenant_id == self.tenant_id,
                ResumeModel.user_id == self.user_id,
                ResumeModel.content_hash == content_hash,
            )
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_recent(self, limit: int = 100) -> list[StoredResume]:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.tenant_id == self.tenant_id, ResumeModel.user_id == self.user_id)
            .order_by(ResumeModel.updated_at.desc())
            .limit(limit)
        )
        return [_to_domain(model) for model in result.scalars().all()]

    async def delete_by_id(self, resume_id: str) -> StoredResume | None:
        model = await self.session.get(ResumeModel, uuid.UUID(resume_id))
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            return None
        deleted = _to_domain(model)
        await self.session.delete(model)
        await self.session.flush()
        return deleted

    async def upsert(
        self,
        *,
        filename: str,
        file_type: str,
        content_hash: str,
        summary: str,
        text: str,
        truncated: bool,
        source_path: str | None,
        object_bucket: str | None,
        object_key: str | None,
        size_bytes: int,
        metadata: dict | None = None,
    ) -> StoredResume:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.tenant_id == self.tenant_id,
                ResumeModel.user_id == self.user_id,
                ResumeModel.content_hash == content_hash,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = ResumeModel(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                filename=filename,
                file_type=file_type,
                content_hash=content_hash,
                summary=summary,
                text=text,
                truncated=truncated,
                source_path=source_path,
                object_bucket=object_bucket,
                object_key=object_key,
                size_bytes=size_bytes,
                metadata_json=metadata or {},
            )
            self.session.add(model)
        else:
            model.filename = filename
            model.file_type = file_type
            model.summary = summary
            model.text = text
            model.truncated = truncated
            model.source_path = source_path
            model.object_bucket = object_bucket or model.object_bucket
            model.object_key = object_key or model.object_key
            model.size_bytes = size_bytes
            model.metadata_json = metadata or model.metadata_json or {}
        await self.session.flush()
        return _to_domain(model)


def _to_domain(model: ResumeModel) -> StoredResume:
    return StoredResume(
        id=str(model.id),
        filename=model.filename,
        file_type=model.file_type,
        summary=model.summary,
        text=model.text,
        truncated=model.truncated,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
        source_path=model.source_path,
        content_hash=model.content_hash,
        object_key=model.object_key,
        object_bucket=model.object_bucket,
        size_bytes=model.size_bytes,
    )
