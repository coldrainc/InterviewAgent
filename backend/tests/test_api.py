import base64
import hashlib
import hmac
import json

import pytest

from fastapi.testclient import TestClient

from interview_agent.core.config import InterviewConfig
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import SessionRequest, apply_session_request, create_app


def _register_headers(client: TestClient, email: str = "candidate@example.com") -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "passw0rd!",
            "display_name": email.split("@")[0],
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_apply_session_request_updates_resume_profile() -> None:
    config = InterviewConfig()
    request = SessionRequest(
        candidate_name="张三",
        target_role="AI Agent 工程师",
        seniority="高级",
        resume_summary="5 年后端经验，做过 RAG 和 Agent 平台。",
        resume_text="完整简历内容",
        project_experience="主导知识库问答、评测和上线治理。",
        interview_goal="重点深挖真实项目。",
        focus_areas=["简历项目深挖", "Agent 工具调用"],
    )

    updated = apply_session_request(config, request)

    assert updated.candidate.name == "张三"
    assert updated.candidate.target_role == "AI Agent 工程师"
    assert updated.candidate.resume_text == "完整简历内容"
    assert updated.candidate.project_experience == "主导知识库问答、评测和上线治理。"
    assert updated.candidate.interview_goal == "重点深挖真实项目。"
    assert updated.focus_areas == ["简历项目深挖", "Agent 工具调用"]


def test_apply_session_request_ignores_blank_values() -> None:
    config = InterviewConfig()
    request = SessionRequest(candidate_name="  ", target_role="  RAG 工程师  ")

    updated = apply_session_request(config, request)

    assert updated.candidate.name == config.candidate.name
    assert updated.candidate.target_role == "RAG 工程师"


def test_apply_session_request_updates_mode_and_industry() -> None:
    config = InterviewConfig()
    request = SessionRequest(mode="candidate", industry="fintech")

    updated = apply_session_request(config, request)

    assert updated.mode == "candidate"
    assert updated.industry == "fintech"


def test_api_exposes_industry_metadata(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.get("/metadata/industries?target_role=Agent%20%E5%B7%A5%E7%A8%8B%E5%B8%88")

    assert response.status_code == 200
    payload = response.json()
    values = {item["value"] for item in payload}
    assert {"internet", "ai_application", "ecommerce", "fintech", "enterprise_saas"} <= values
    ai_option = next(item for item in payload if item["value"] == "ai_application")
    assert "Agent 工程师" in " ".join(ai_option["recommended_focus_areas"])
    assert ai_option["production_signals"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_resume_endpoints_use_database_storage(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 李四\n\n做过 AgentLoop 和 RAG 系统。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        headers = _register_headers(client, "resume-owner@example.com")
        response = client.post(
            "/resumes",
            headers=headers,
            json={
                "filename": "resume.md",
                "content_base64": encoded,
                "source_path": "/tmp/resume.md",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["filename"] == "resume.md"

        list_response = client.get("/resumes", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == payload["id"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_token_auth_and_tenant_isolation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "token-a:tenant_a,token-b:tenant_b")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 王五\n\n做过 RAG 系统。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        unauthorized = client.get("/resumes")
        assert unauthorized.status_code == 401

        created = client.post(
            "/resumes",
            headers={"Authorization": "Bearer token-a"},
            json={"filename": "resume.md", "content_base64": encoded},
        )
        assert created.status_code == 200
        resume_id = created.json()["id"]

        tenant_b_list = client.get("/resumes", headers={"Authorization": "Bearer token-b"})
        assert tenant_b_list.status_code == 200
        assert tenant_b_list.json() == []

        tenant_b_get = client.get(
            f"/resumes/{resume_id}",
            headers={"Authorization": "Bearer token-b"},
        )
        assert tenant_b_get.status_code == 404

    import asyncio

    asyncio.run(engine.dispose())


def test_api_dev_login_issues_client_token_and_me(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("INTERVIEW_AUTH_DEV_LOGIN_ENABLED", "true")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        login = client.post(
            "/auth/dev-login",
            json={
                "user_id": "ios-user",
                "tenant_id": "tenant_ios",
                "display_name": "iOS 用户",
                "platform": "ios",
            },
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["tenant_id"] == "tenant_ios"
        assert me.json()["user_id"] == "ios-user"
        assert me.json()["platform"] == "ios"
        assert me.json()["authenticated"] is True

    import asyncio

    asyncio.run(engine.dispose())


def test_api_provider_login_requires_real_provider_when_mock_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED", "false")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post("/auth/wechat/login", json={"code": "mock-code"})
        assert response.status_code == 501

    import asyncio

    asyncio.run(engine.dispose())


def test_api_session_history_delete_and_restore(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "history@example.com")
        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        list_response = client.get("/sessions", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == session_id

        detail = client.get(f"/sessions/{session_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["turns"]

        from interview_agent.interfaces import api as api_module

        api_module.sessions.pop(session_id, None)
        restored_message = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我负责 RAG 检索、embedding、rerank、监控和灰度上线，p95 延迟控制在 800ms。"},
        )
        assert restored_message.status_code == 200

        deleted = client.delete(f"/sessions/{session_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        missing = client.get(f"/sessions/{session_id}", headers=headers)
        assert missing.status_code == 404

    import asyncio

    asyncio.run(engine.dispose())


def test_api_wechat_login_exchanges_code(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WECHAT_MINIAPP_APP_ID", "wx-app")
    monkeypatch.setenv("WECHAT_MINIAPP_APP_SECRET", "wx-secret")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"openid": "openid-123", "session_key": "session-key"}

    def fake_get(url, params, timeout):
        assert params["appid"] == "wx-app"
        assert params["secret"] == "wx-secret"
        assert params["js_code"] == "login-code"
        return FakeResponse()

    monkeypatch.setattr("interview_agent.infrastructure.auth_providers.requests.get", fake_get)

    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post("/auth/wechat/login", json={"code": "login-code"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["user_id"] == "wechat:openid-123"
        assert payload["platform"] == "miniapp"
        assert payload["access_token"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_stream_message_returns_sse_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "stream@example.com")
        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        response = client.post(
            f"/sessions/{session_id}/stream",
            headers=headers,
            json={"message": "我负责 RAG embedding rerank 灰度上线和监控，p95 延迟 800ms。"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        text = response.text
        assert "event: tool.notice" in text
        assert "event: message.done" in text
        assert "session_id" in text

    import asyncio

    asyncio.run(engine.dispose())


def test_api_account_trial_recharge_and_usage_billing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "billing-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        models = client.get("/metadata/models")
        assert models.status_code == 200
        model_payload = models.json()
        model_ids = {item["id"] for item in model_payload}
        assert "gpt-5.5" in model_ids
        assert "gpt-4o-mini" not in model_ids
        assert "claude-fable-5" in model_ids
        assert "deepseek-chat" not in model_ids
        assert all("runtime_supported" in item for item in model_payload)
        assert all("category" in item for item in model_payload)

        registered = client.post(
            "/auth/register",
            json={
                "email": "candidate@example.com",
                "password": "passw0rd!",
                "display_name": "候选人",
            },
        )
        assert registered.status_code == 200
        token = registered.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert registered.json()["trial_uses_remaining"] == 2

        first = client.post(
            "/sessions",
            headers=headers,
            json={"offline": True, "model_id": "gpt-4o-mini"},
        )
        assert first.status_code == 200
        assert first.json()["usage"]["trial_used"] is True
        assert first.json()["usage"]["trial_uses_remaining"] == 1
        session_id = first.json()["session_id"]

        second = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我负责 RAG embedding rerank 灰度上线和监控，p95 延迟 800ms，成本下降 30%。"},
        )
        assert second.status_code == 200
        assert second.json()["usage"]["trial_used"] is True
        assert second.json()["usage"]["trial_uses_remaining"] == 0

        blocked = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我继续补充一次上线复盘，包含监控、回滚和安全治理。"},
        )
        assert blocked.status_code == 402

        recharged = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "1.5", "external_order_id": "order-001"},
        )
        assert recharged.status_code == 200
        assert recharged.json()["credit_balance_micros"] == 1_500_000

        paid = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我继续补充一次上线复盘，包含监控、回滚和安全治理。"},
        )
        assert paid.status_code == 200
        usage = paid.json()["usage"]
        assert usage["trial_used"] is False
        assert usage["cost_credits_micros"] > 0
        assert usage["credit_balance_micros"] < 1_500_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_rejects_oversized_upload_and_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_MAX_UPLOAD_BYTES", "8")
    monkeypatch.setenv("INTERVIEW_MAX_MESSAGE_CHARS", "12")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "limits@example.com")
        upload = client.post(
            "/resumes",
            headers=headers,
            json={
                "filename": "resume.md",
                "content_base64": base64.b64encode(b"this is too long").decode("ascii"),
            },
        )
        assert upload.status_code == 413

        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        message = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "这是一段明显超过长度限制的消息"},
        )
        assert message.status_code == 413


def test_api_user_isolation_within_same_tenant(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 用户 A\n\n负责生产级 RAG。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        user_a = _register_headers(client, "user-a@example.com")
        user_b = _register_headers(client, "user-b@example.com")

        created_resume = client.post(
            "/resumes",
            headers=user_a,
            json={"filename": "resume.md", "content_base64": encoded},
        )
        assert created_resume.status_code == 200
        resume_id = created_resume.json()["id"]

        created_session = client.post("/sessions", headers=user_a, json={"offline": True})
        assert created_session.status_code == 200
        session_id = created_session.json()["session_id"]

        assert client.get("/resumes", headers=user_b).json() == []
        assert client.get(f"/resumes/{resume_id}", headers=user_b).status_code == 404
        assert client.get("/sessions", headers=user_b).json() == []
        assert client.get(f"/sessions/{session_id}", headers=user_b).status_code == 404

    import asyncio

    asyncio.run(engine.dispose())


def test_api_signed_payment_webhook_applies_and_is_idempotent(monkeypatch, tmp_path) -> None:
    secret = "payment-secret-long-enough"
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    payload = {
        "tenant_id": "default",
        "user_id": "email:pay@example.com",
        "amount_credits": "2.5",
        "payment_provider": "stripe",
        "external_order_id": "pay-order-001",
        "status": "paid",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        first = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert first.status_code == 200
        assert first.json()["applied"] is True
        assert first.json()["account"]["credit_balance_micros"] == 2_500_000

        second = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert second.status_code == 200
        assert second.json()["applied"] is False
        assert second.json()["account"]["credit_balance_micros"] == 2_500_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_payment_order_requires_webhook_to_credit(monkeypatch, tmp_path) -> None:
    secret = "payment-secret-long-enough"
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "order-flow@example.com")
        order = client.post(
            "/payments/orders",
            headers=headers,
            json={
                "amount_credits": "3",
                "payment_provider": "stripe",
                "external_order_id": "pay-order-created-001",
            },
        )
        assert order.status_code == 200
        assert order.json()["status"] == "pending"
        assert order.json()["created"] is True

        account_before = client.get("/account", headers=headers)
        assert account_before.status_code == 200
        assert account_before.json()["credit_balance_micros"] == 0

        payload = {
            "tenant_id": "default",
            "user_id": "email:order-flow@example.com",
            "amount_credits": "3",
            "payment_provider": "stripe",
            "external_order_id": "pay-order-created-001",
            "status": "paid",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        paid = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert paid.status_code == 200
        assert paid.json()["applied"] is True
        assert paid.json()["account"]["credit_balance_micros"] == 3_000_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_payment_webhook_rejects_bad_signature(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", "payment-secret-long-enough")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post(
            "/payments/webhook",
            json={
                "tenant_id": "default",
                "user_id": "email:pay@example.com",
                "amount_credits": "2.5",
                "payment_provider": "stripe",
                "external_order_id": "pay-order-002",
                "status": "paid",
            },
            headers={"X-Payment-Signature": "bad"},
        )
        assert response.status_code == 401

    import asyncio

    asyncio.run(engine.dispose())


def test_api_manual_recharge_forbidden_when_mock_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_ALLOW_MOCK_RECHARGE", "false")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "blocked-recharge@example.com")
        response = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "1", "external_order_id": "manual-blocked"},
        )
        assert response.status_code == 403

    import asyncio

    asyncio.run(engine.dispose())


def test_api_production_security_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_ENV", "production")
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "false")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "short")
    monkeypatch.setenv("INTERVIEW_ALLOW_MOCK_RECHARGE", "true")
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", "")
    monkeypatch.setenv("INTERVIEW_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("INTERVIEW_ALLOWED_ORIGINS", "*")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")

    with pytest.raises(RuntimeError, match="生产安全配置未通过"):
        create_app(object_storage=storage, database_engine=engine)

    import asyncio

    asyncio.run(engine.dispose())

    import asyncio

    asyncio.run(engine.dispose())
