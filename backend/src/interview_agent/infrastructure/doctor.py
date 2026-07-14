from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from pathlib import Path

import requests
from sqlalchemy import text

from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import create_object_storage
from interview_agent.infrastructure.settings import AppSettings, load_settings


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def run_doctor(
    *,
    index_path: Path,
    vector_store_metadata_path: Path,
    embedding_service_url: str,
    qdrant_url: str,
    qdrant_collection: str,
    settings: AppSettings | None = None,
) -> list[CheckResult]:
    app_settings = settings or load_settings()
    results = [
        _check_database(app_settings.database_url),
        _check_object_storage(app_settings),
        _check_file("RAG index", index_path),
        _check_file("Vector store metadata", vector_store_metadata_path),
        _check_embedding_service(embedding_service_url),
        _check_qdrant(qdrant_url, qdrant_collection),
    ]
    return results


def _check_database(database_url: str) -> CheckResult:
    async def probe() -> None:
        engine = create_engine_for_url(database_url)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("select 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.run(probe())
    except Exception as exc:
        return CheckResult("PostgreSQL", False, str(exc))
    return CheckResult("PostgreSQL", True, database_url)


def _check_object_storage(settings: AppSettings) -> CheckResult:
    try:
        storage = create_object_storage(settings)
        storage.ensure_ready()
    except Exception as exc:
        return CheckResult("ObjectStorage", False, str(exc))
    return CheckResult(
        "ObjectStorage",
        True,
        f"{settings.object_storage_backend} bucket={storage.bucket}",
    )


def _check_file(name: str, path: Path) -> CheckResult:
    if not path.exists():
        return CheckResult(name, False, f"missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult(name, False, f"invalid json: {exc}")
    count = payload.get("chunk_count") or payload.get("embedding_model") or "ok"
    return CheckResult(name, True, f"{path} ({count})")


def _check_embedding_service(url: str) -> CheckResult:
    try:
        response = requests.get(f"{url.rstrip('/')}/health", timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return CheckResult("EmbeddingService", False, str(exc))
    return CheckResult(
        "EmbeddingService",
        payload.get("status") == "ok",
        f"{url} model={payload.get('model')}",
    )


def _check_qdrant(url: str, collection: str) -> CheckResult:
    try:
        response = requests.get(f"{url.rstrip('/')}/collections/{collection}", timeout=5)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {})
    except Exception as exc:
        return CheckResult("Qdrant", False, str(exc))
    return CheckResult(
        "Qdrant",
        payload.get("status") == "ok",
        f"{url} collection={collection} points={result.get('points_count')}",
    )
