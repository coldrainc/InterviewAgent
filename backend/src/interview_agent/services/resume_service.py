from __future__ import annotations

import base64
import hashlib
import asyncio
import binascii
import mimetypes
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.resume import StoredResume
from interview_agent.infrastructure.object_storage import ObjectStorage
from interview_agent.infrastructure.resume_parser import parse_resume_bytes
from interview_agent.repositories.resume_repository import ResumeRepository


class ResumeService:
    def __init__(
        self,
        session: AsyncSession,
        object_storage: ObjectStorage,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        *,
        max_upload_bytes: int | None = None,
        store_source_path: bool = False,
    ) -> None:
        self.repository = ResumeRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.object_storage = object_storage
        self.max_upload_bytes = max_upload_bytes
        self.store_source_path = store_source_path

    async def save_base64(
        self,
        filename: str,
        content_base64: str,
        source_path: str | None = None,
    ) -> StoredResume:
        try:
            raw = base64.b64decode(content_base64, validate=True)
        except binascii.Error as exc:
            raise ValueError("简历文件 base64 内容无效。") from exc
        return await self.save_bytes(filename, raw, source_path=source_path)

    async def save_bytes(
        self,
        filename: str,
        content: bytes,
        source_path: str | None = None,
    ) -> StoredResume:
        if self.max_upload_bytes is not None and len(content) > self.max_upload_bytes:
            raise ValueError(f"简历文件过大，最大允许 {self.max_upload_bytes} 字节。")
        content_hash = hashlib.sha256(content).hexdigest()
        parsed = parse_resume_bytes(filename, content)
        suffix = Path(parsed.filename).suffix.lower() or ".bin"
        object_key = f"resumes/{content_hash}{suffix}"
        content_type = _content_type(parsed.filename)

        storage_ref = await asyncio.to_thread(
            self.object_storage.put_bytes,
            object_key,
            content,
            content_type,
        )
        return await self.repository.upsert(
            filename=parsed.filename,
            file_type=parsed.file_type,
            content_hash=content_hash,
            summary=parsed.summary,
            text=parsed.text,
            truncated=parsed.truncated,
            source_path=source_path if self.store_source_path else None,
            object_bucket=storage_ref.bucket,
            object_key=storage_ref.key,
            size_bytes=storage_ref.size_bytes,
            metadata={
                "content_type": content_type,
                "parser": "resume_parser.v1",
            },
        )

    async def list(self) -> list[StoredResume]:
        return await self.repository.list_recent()

    async def get(self, resume_id: str) -> StoredResume | None:
        return await self.repository.get_by_id(resume_id)

    async def delete(self, resume_id: str) -> bool:
        deleted = await self.repository.delete_by_id(resume_id)
        if not deleted:
            return False
        if deleted.object_bucket and deleted.object_key:
            await asyncio.to_thread(
                self.object_storage.delete_object,
                deleted.object_bucket,
                deleted.object_key,
            )
        return True


def _content_type(filename: str) -> str:
    guessed, _encoding = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
