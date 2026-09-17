from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from interview_agent.infrastructure.db.models import CreditLedgerModel, UserAccountModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.infrastructure.security import issue_client_token
from interview_agent.infrastructure.settings import load_settings
from interview_agent.interfaces.api import create_app


def _token(user_id: str, role: str) -> dict[str, str]:
    token, _ = issue_client_token(
        load_settings(), tenant_id="default", user_id=user_id, platform="test", role=role
    )
    return {"Authorization": f"Bearer {token}"}


def _app(tmp_path):
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    app = create_app(
        object_storage=LocalObjectStorage(root=tmp_path / "objects", bucket="admin-test"),
        database_engine=engine,
        start_background_workers=False,
    )
    return app, engine


def test_admin_console_is_hidden_from_regular_users(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/admin/dashboard", headers=_token("regular-user", "user"))
        assert response.status_code == 403

    import asyncio
    asyncio.run(engine.dispose())


def test_admin_can_manage_user_balance_status_and_audit(tmp_path) -> None:
    app, engine = _app(tmp_path)
    admin = _token("admin-user", "admin")
    user = _token("managed-user", "user")
    with TestClient(app) as client:
        assert client.get("/account", headers=user).status_code == 200
        users = client.get("/admin/users", headers=admin)
        assert users.status_code == 200
        assert any(item["user_id"] == "managed-user" for item in users.json())

        adjusted = client.post(
            "/admin/users/managed-user/balance-adjustments",
            headers=admin,
            json={"amount_credits": "12.5", "reason": "测试运营补偿"},
        )
        assert adjusted.status_code == 200, adjusted.text
        assert adjusted.json()["credit_balance"] == "12.5"

        suspended = client.patch(
            "/admin/users/managed-user/status",
            headers=admin,
            json={"status": "suspended", "reason": "测试风控停用"},
        )
        assert suspended.status_code == 200
        assert client.get("/account", headers=user).status_code == 401

        audit = client.get("/admin/audit", headers=admin)
        assert audit.status_code == 200
        actions = {item["action"] for item in audit.json()}
        assert {"user_balance_adjusted", "user_status_updated"}.issubset(actions)

    import asyncio

    async def verify_ledger() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            ledger = (await session.execute(select(CreditLedgerModel))).scalar_one()
            assert ledger.kind == "admin_adjustment"
            assert ledger.amount_micros == 12_500_000

    asyncio.run(verify_ledger())
    asyncio.run(engine.dispose())


def test_model_policy_controls_catalog_and_pricing(tmp_path) -> None:
    app, engine = _app(tmp_path)
    admin = _token("model-admin", "admin")
    user = _token("model-user", "user")
    with TestClient(app) as client:
        disabled = client.put(
            "/admin/models/gpt-5.5",
            headers=admin,
            json={
                "enabled": False,
                "is_default": False,
                "input_usd_per_1m": "7.5",
                "output_usd_per_1m": "35",
            },
        )
        assert disabled.status_code == 200, disabled.text
        catalog = client.get("/metadata/models", headers=user)
        assert catalog.status_code == 200
        assert "gpt-5.5" not in {item["id"] for item in catalog.json()}

        enabled = client.put(
            "/admin/models/gpt-5.5",
            headers=admin,
            json={
                "enabled": True,
                "is_default": True,
                "input_usd_per_1m": "7.5",
                "output_usd_per_1m": "35",
            },
        )
        assert enabled.status_code == 200
        models = client.get("/admin/models", headers=admin).json()
        model = next(item for item in models if item["id"] == "gpt-5.5")
        assert model["is_default"] is True
        assert model["input_usd_per_1m"] == "7.5"
        assert set(model) >= {"credential_status"}
        assert "api_key" not in model

    import asyncio
    asyncio.run(engine.dispose())


def test_admin_plans_are_persisted_and_editable(tmp_path) -> None:
    app, engine = _app(tmp_path)
    admin = _token("plan-admin", "admin")
    with TestClient(app) as client:
        plans = client.get("/admin/plans", headers=admin)
        assert plans.status_code == 200
        assert len(plans.json()) == 3
        starter = plans.json()[0]
        starter["price_credits"] = "29"
        updated = client.put(f"/admin/plans/{starter['code']}", headers=admin, json=starter)
        assert updated.status_code == 200, updated.text
        assert updated.json()["price_credits"] == "29"

        public_plans = client.get("/billing/plans")
        assert public_plans.status_code == 200
        assert next(item for item in public_plans.json() if item["code"] == starter["code"])["price_credits"] == "29"

    import asyncio
    asyncio.run(engine.dispose())


def test_payment_plan_uses_server_side_price_and_credited_amount(tmp_path) -> None:
    app, engine = _app(tmp_path)
    admin = _token("payment-admin", "admin")
    user = _token("payment-user", "user")
    with TestClient(app) as client:
        starter = client.get("/admin/plans", headers=admin).json()[0]
        starter.update({"price_credits": "19", "included_credits": "30"})
        assert client.put(f"/admin/plans/{starter['code']}", headers=admin, json=starter).status_code == 200

        mismatched = client.post(
            "/payments/orders",
            headers=user,
            json={"amount_credits": "1", "plan_code": starter["code"], "payment_provider": "mock"},
        )
        assert mismatched.status_code == 400

        created = client.post(
            "/payments/orders",
            headers=user,
            json={"amount_credits": "19", "plan_code": starter["code"], "payment_provider": "mock"},
        )
        assert created.status_code == 200, created.text
        assert created.json()["amount_credits"] == "19"
        assert created.json()["credited_amount"] == "30"

    import asyncio
    asyncio.run(engine.dispose())
