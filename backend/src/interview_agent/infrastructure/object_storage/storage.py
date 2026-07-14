from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from interview_agent.infrastructure.settings import AppSettings, load_settings


@dataclass(frozen=True)
class ObjectStorageRef:
    bucket: str
    key: str
    size_bytes: int


class ObjectStorage(Protocol):
    bucket: str

    def ensure_ready(self) -> None:
        ...

    def put_bytes(self, key: str, content: bytes, content_type: str) -> ObjectStorageRef:
        ...

    def delete_object(self, bucket: str, key: str) -> None:
        ...


class LocalObjectStorage:
    def __init__(self, root: Path = Path(".interview_agent/object_storage"), bucket: str = "local") -> None:
        self.root = root
        self.bucket = bucket

    def ensure_ready(self) -> None:
        (self.root / self.bucket).mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, content: bytes, content_type: str) -> ObjectStorageRef:
        self.ensure_ready()
        path = self.root / self.bucket / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ObjectStorageRef(bucket=self.bucket, key=key, size_bytes=len(content))

    def delete_object(self, bucket: str, key: str) -> None:
        path = self.root / bucket / key
        if path.exists():
            path.unlink()


class MinioObjectStorage:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or load_settings()
        self.bucket = self.settings.object_storage_bucket
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError("MinIO 对象存储需要安装 minio 依赖。") from exc

        self.client = Minio(
            self.settings.object_storage_endpoint,
            access_key=self.settings.object_storage_access_key,
            secret_key=self.settings.object_storage_secret_key,
            secure=self.settings.object_storage_secure,
        )

    def ensure_ready(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_bytes(self, key: str, content: bytes, content_type: str) -> ObjectStorageRef:
        self.ensure_ready()
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return ObjectStorageRef(bucket=self.bucket, key=key, size_bytes=len(content))

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.remove_object(bucket, key)


def create_object_storage(settings: AppSettings | None = None) -> ObjectStorage:
    resolved = settings or load_settings()
    if resolved.object_storage_backend == "local":
        return LocalObjectStorage(bucket=resolved.object_storage_bucket)
    if resolved.object_storage_backend == "minio":
        return MinioObjectStorage(resolved)
    raise ValueError(f"Unsupported object storage backend: {resolved.object_storage_backend}")
