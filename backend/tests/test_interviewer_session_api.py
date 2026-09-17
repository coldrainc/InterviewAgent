from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from interview_agent.core.guardrails import HarnessGuardrails
from interview_agent.core.harness_result import HarnessResult
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces import api as api_module
from interview_agent.interfaces.api import create_app, sessions


class _OfflineHarness:
    def __init__(self) -> None:
        self.guardrails = HarnessGuardrails()

    def generate_result(self, stage, state) -> HarnessResult:
        return HarnessResult(text=f"offline response for {stage.value}")

    def generate_result_stream(self, stage, state, on_delta) -> HarnessResult:
        result = self.generate_result(stage, state)
        on_delta(result.text)
        return result

    def respond_to_candidate_question_result(self, question, state) -> HarnessResult:
        return HarnessResult(text="offline clarification")

    def respond_to_candidate_question_result_stream(self, question, state, on_delta) -> HarnessResult:
        result = self.respond_to_candidate_question_result(question, state)
        on_delta(result.text)
        return result


def _register_headers(client: TestClient, email: str) -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": f"203.0.113.{ip_suffix}"},
        json={
            "email": email,
            "password": "passw0rd!",
            "display_name": email.split("@")[0],
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_interviewer_kit_session_link_is_owned_persisted_and_restored(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(api_module, "_create_harness", lambda *args, **kwargs: _OfflineHarness())
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="interviewer-api")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        owner = _register_headers(client, "kit-owner@example.com")
        other_user = _register_headers(client, "kit-other@example.com")
        kit_response = client.post(
            "/interviewer-workspace/kits",
            headers=owner,
            json={"target_role": "Backend Engineer"},
        )
        assert kit_response.status_code == 200
        kit_id = kit_response.json()["id"]

        forbidden = client.post(
            "/sessions",
            headers=other_user,
            json={"offline": True, "interviewer_kit_id": kit_id},
        )
        assert forbidden.status_code == 404

        created = client.post(
            "/sessions",
            headers=owner,
            json={"offline": True, "interviewer_kit_id": kit_id},
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        detail = client.get(f"/sessions/{session_id}", headers=owner)
        assert detail.status_code == 200
        assert detail.json()["interviewer_kit_id"] == kit_id

        sessions.pop(session_id, None)
        restored = client.post(
            f"/sessions/{session_id}/messages",
            headers=owner,
            json={"message": "我负责了服务稳定性建设。"},
        )
        assert restored.status_code == 200
        assert sessions[session_id].interviewer_kit_id == kit_id

    import asyncio

    asyncio.run(engine.dispose())
