from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.privacy.deletion_service import DataDeletionService
from interview_agent.privacy.models import DataDeletionRequestModel


def _register(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "privacy-api@example.com",
            "password": "passw0rd!",
            "display_name": "Privacy API",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["access_token"], body["user_id"]


def test_privacy_export_schedule_get_and_cancel(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "privacy-test-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="privacy-api")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        token, user_id = _register(client)
        headers = {"Authorization": f"Bearer {token}"}

        invalid_confirmation = client.post(
            "/privacy/deletion",
            headers=headers,
            json={"confirmation": "delete", "reason": "must not be accepted"},
        )
        assert invalid_confirmation.status_code == 422

        exported = client.get("/privacy/export", headers=headers)
        assert exported.status_code == 200, exported.text
        payload = exported.json()
        assert payload["user_id"] == user_id
        assert "password_hash" not in payload["data"]["account"]["user_accounts"][0]

        scheduled = client.post(
            "/privacy/deletion",
            headers=headers,
            json={"confirmation": "DELETE", "reason": "API lifecycle test"},
        )
        assert scheduled.status_code == 200, scheduled.text
        assert scheduled.json()["status"] == "scheduled"

        current = client.get("/privacy/deletion", headers=headers)
        assert current.status_code == 200
        assert current.json()["request"]["id"] == scheduled.json()["id"]
        assert current.json()["cooling_off_days"] == 7

        cancelled = client.delete("/privacy/deletion", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

    asyncio.run(engine.dispose())


def test_executed_deletion_rejects_old_token_and_password_login(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "privacy-test-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="privacy-api")
    app = create_app(object_storage=storage, database_engine=engine)

    async def execute_deletion(user_id: str) -> None:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            request = await db.scalar(
                select(DataDeletionRequestModel).where(DataDeletionRequestModel.user_id == user_id)
            )
            request.execute_after = datetime.now(timezone.utc) - timedelta(seconds=1)
            await DataDeletionService(
                db,
                tenant_id="default",
                user_id=user_id,
                object_storage=storage,
            ).execute_if_due()
            await db.commit()

    with TestClient(app) as client:
        token, user_id = _register(client)
        headers = {"Authorization": f"Bearer {token}"}
        scheduled = client.post(
            "/privacy/deletion",
            headers=headers,
            json={"confirmation": "DELETE", "reason": "confirmed"},
        )
        assert scheduled.status_code == 200

        asyncio.run(execute_deletion(user_id))

        old_token = client.get("/me", headers=headers)
        assert old_token.status_code == 401
        assert old_token.json()["message"] == "账号已删除。"

        password_login = client.post(
            "/auth/login",
            json={"email": "privacy-api@example.com", "password": "passw0rd!"},
        )
        assert password_login.status_code == 401

    asyncio.run(engine.dispose())


def test_application_error_envelope_preserves_structured_conflict_details(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    app = create_app(
        object_storage=LocalObjectStorage(root=tmp_path / "objects", bucket="privacy-api"),
        database_engine=engine,
    )
    detail = {
        "code": "version_conflict",
        "message": "stale version",
        "expected_version": 1,
        "current_version": 2,
        "current_task": {"id": "task-1", "status": "in_progress"},
        "resolution": "refresh_and_retry",
    }

    @app.get("/__test__/structured-conflict")
    async def structured_conflict() -> None:
        raise HTTPException(status_code=409, detail=detail)

    with TestClient(app) as client:
        response = client.get("/__test__/structured-conflict")

    assert response.status_code == 409
    assert response.json()["details"] == detail
    asyncio.run(engine.dispose())
