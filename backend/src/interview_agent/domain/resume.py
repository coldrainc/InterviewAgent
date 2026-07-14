from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StoredResume:
    id: str
    filename: str
    file_type: str
    summary: str
    text: str
    truncated: bool
    created_at: str
    updated_at: str
    source_path: str | None = None
    content_hash: str | None = None
    object_key: str | None = None
    object_bucket: str | None = None
    size_bytes: int | None = None


def stored_resume_to_payload(resume: StoredResume) -> dict:
    payload = asdict(resume)
    payload.pop("content_hash", None)
    payload.pop("object_key", None)
    payload.pop("object_bucket", None)
    payload.pop("size_bytes", None)
    return payload
