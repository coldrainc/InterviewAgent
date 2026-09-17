from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import ClientRequestLogModel, SecurityEventModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.infrastructure.security import issue_client_token
from interview_agent.infrastructure.settings import load_settings
from interview_agent.interfaces.api import create_app
from interview_agent.services import client_request_log_service


def test_request_audit_records_client_source_and_platform_mismatch(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    app = create_app(
        object_storage=LocalObjectStorage(root=tmp_path / "objects", bucket="audit-test"),
        database_engine=engine,
    )
    token, _ = issue_client_token(
        load_settings(),
        tenant_id="tenant-audit",
        user_id="audit-user",
        platform="ios",
    )
    request_id = "client-audit-request-1"

    with TestClient(app) as client:
        response = client.get(
            "/health?resume=private-resume-content",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Client-Platform": "android",
                "X-Client-Version": "2.3.4-beta.1",
                "X-Client-Request-Id": request_id,
                "X-Request-ID": request_id,
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id

    async def _read_rows():
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            request_log = (
                await session.execute(
                    select(ClientRequestLogModel).where(ClientRequestLogModel.request_id == request_id)
                )
            ).scalar_one()
            mismatch = (
                await session.execute(
                    select(SecurityEventModel).where(
                        SecurityEventModel.request_id == request_id,
                        SecurityEventModel.event_type == "platform_mismatch",
                    )
                )
            ).scalar_one()
            return request_log, mismatch

    request_log, mismatch = asyncio.run(_read_rows())
    assert request_log.tenant_id == "tenant-audit"
    assert request_log.user_id == "audit-user"
    assert request_log.auth_platform == "ios"
    assert request_log.client_platform == "android"
    assert request_log.client_version == "2.3.4-beta.1"
    assert request_log.platform_matched is False
    assert request_log.path == "/health"
    assert "private-resume-content" not in request_log.path
    assert mismatch.metadata_json == {
        "auth_platform": "ios",
        "client_platform": "android",
        "client_version": "2.3.4-beta.1",
        "path": "/health",
    }
    asyncio.run(engine.dispose())


def test_anonymous_request_audit_sanitizes_untrusted_metadata(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    app = create_app(
        object_storage=LocalObjectStorage(root=tmp_path / "objects", bucket="audit-anonymous"),
        database_engine=engine,
    )

    with TestClient(app) as client:
        response = client.get(
            "/health?answer=do-not-store",
            headers={
                "X-Client-Platform": "../../ios<script>",
                "X-Client-Version": " 1.2.3\nAuthorization: secret ",
                "X-Client-Request-Id": "request id with spaces",
            },
        )

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]

    async def _read_log():
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return (
                await session.execute(
                    select(ClientRequestLogModel).where(ClientRequestLogModel.request_id == request_id)
                )
            ).scalar_one()

    request_log = asyncio.run(_read_log())
    assert request_id == "requestidwithspaces"
    assert request_log.user_id is None
    assert request_log.auth_platform == "unknown"
    assert request_log.client_platform == "unknown"
    assert request_log.client_version == "unknown"
    assert request_log.platform_matched is None
    assert request_log.path == "/health"
    assert "do-not-store" not in request_log.path
    asyncio.run(engine.dispose())


def test_request_log_failure_never_breaks_product_request(monkeypatch, tmp_path) -> None:
    async def _fail(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(client_request_log_service, "record_client_request", _fail)
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    app = create_app(
        object_storage=LocalObjectStorage(root=tmp_path / "objects", bucket="audit-failure"),
        database_engine=engine,
    )
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"X-Client-Platform": "web", "X-Client-Version": "0.1.0"},
        )
    assert response.status_code == 200
    asyncio.run(engine.dispose())


def test_request_log_schema_has_no_payload_or_credential_columns() -> None:
    columns = set(ClientRequestLogModel.__table__.columns.keys())
    assert columns.isdisjoint(
        {
            "body",
            "query",
            "authorization",
            "cookie",
            "resume",
            "answer",
            "conversation",
            "prompt",
        }
    )
