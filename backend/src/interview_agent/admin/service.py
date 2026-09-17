from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.billing import credits_to_micros, default_model_catalog, micros_to_credits
from interview_agent.infrastructure.codex_config import load_codex_model_config
from interview_agent.infrastructure.db.models import (
    ModelPolicyModel,
    RechargeOrderModel,
    SecurityEventModel,
    SubscriptionPlanModel,
    UsageRecordModel,
    UserAccountModel,
    UserRoleAssignmentModel,
)
from interview_agent.infrastructure.model_runtime import resolve_model_runtime
from interview_agent.services.billing_service import BillingError, BillingService
from interview_agent.services.security_service import SecurityService


class AdminConsoleService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, actor_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    async def dashboard(self) -> dict:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=30)
        users = await self.session.scalar(
            select(func.count(UserAccountModel.id)).where(UserAccountModel.tenant_id == self.tenant_id)
        )
        active_users = await self.session.scalar(
            select(func.count(UserAccountModel.id)).where(
                UserAccountModel.tenant_id == self.tenant_id,
                UserAccountModel.status == "active",
            )
        )
        usage = await self.session.execute(
            select(
                func.count(UsageRecordModel.id),
                func.coalesce(func.sum(UsageRecordModel.total_tokens), 0),
                func.coalesce(func.sum(UsageRecordModel.cost_credits_micros), 0),
            ).where(UsageRecordModel.tenant_id == self.tenant_id, UsageRecordModel.created_at >= since)
        )
        usage_count, tokens, cost_micros = usage.one()
        paid = await self.session.execute(
            select(
                func.count(RechargeOrderModel.id),
                func.coalesce(func.sum(RechargeOrderModel.amount_micros), 0),
            ).where(
                RechargeOrderModel.tenant_id == self.tenant_id,
                RechargeOrderModel.status == "paid",
                RechargeOrderModel.created_at >= since,
            )
        )
        paid_count, paid_micros = paid.one()
        alerts = await self.session.scalar(
            select(func.count(SecurityEventModel.id)).where(
                SecurityEventModel.tenant_id == self.tenant_id,
                SecurityEventModel.severity == "critical",
                SecurityEventModel.created_at >= since,
            )
        )
        return {
            "users_total": int(users or 0),
            "users_active": int(active_users or 0),
            "generations_30d": int(usage_count or 0),
            "tokens_30d": int(tokens or 0),
            "usage_credits_30d": str(micros_to_credits(int(cost_micros or 0))),
            "paid_orders_30d": int(paid_count or 0),
            "revenue_credits_30d": str(micros_to_credits(int(paid_micros or 0))),
            "critical_events_30d": int(alerts or 0),
        }

    async def list_users(self, *, query: str = "", status: str = "", limit: int = 20, offset: int = 0) -> list[dict]:
        statement = select(UserAccountModel).where(UserAccountModel.tenant_id == self.tenant_id)
        cleaned_query = query.strip()
        if cleaned_query:
            pattern = f"%{cleaned_query}%"
            statement = statement.where(
                or_(
                    UserAccountModel.user_id.ilike(pattern),
                    UserAccountModel.email.ilike(pattern),
                    UserAccountModel.display_name.ilike(pattern),
                )
            )
        if status in {"active", "suspended", "deleted"}:
            statement = statement.where(UserAccountModel.status == status)
        result = await self.session.execute(
            statement.order_by(UserAccountModel.created_at.desc()).limit(limit).offset(offset)
        )
        accounts = list(result.scalars().all())
        user_ids = [account.user_id for account in accounts]
        if not user_ids:
            return []
        role_rows = await self.session.execute(
            select(UserRoleAssignmentModel).where(
                UserRoleAssignmentModel.tenant_id == self.tenant_id,
                UserRoleAssignmentModel.user_id.in_(user_ids),
                UserRoleAssignmentModel.revoked_at.is_(None),
            )
        )
        roles_by_user: dict[str, list[str]] = {}
        for role in role_rows.scalars().all():
            roles_by_user.setdefault(role.user_id, []).append(role.role)
        return [self._user_payload(account, roles_by_user.get(account.user_id, [])) for account in accounts]

    async def set_user_status(self, *, user_id: str, status: str, reason: str) -> dict:
        account = await self._require_account(user_id, for_update=True)
        if user_id == self.actor_id and status != "active":
            raise BillingError("不能停用当前登录的管理员账号。")
        previous = account.status
        account.status = status
        revoked_tokens = 0
        if status != "active":
            revoked_tokens = await SecurityService(
                self.session, tenant_id=self.tenant_id
            ).revoke_user_refresh_tokens(user_id)
        await self._audit(
            "user_status_updated",
            target=user_id,
            details={"from": previous, "to": status, "reason": reason, "revoked_tokens": revoked_tokens},
        )
        return self._user_payload(account, [])

    async def adjust_balance(self, *, user_id: str, amount: Decimal, reason: str) -> dict:
        if amount == 0:
            raise BillingError("余额调整金额不能为 0。")
        snapshot = await BillingService(self.session).adjust_balance(
            tenant_id=self.tenant_id,
            user_id=user_id,
            amount_credits=amount,
            actor_id=self.actor_id,
            reason=reason,
        )
        await self._audit(
            "user_balance_adjusted",
            target=user_id,
            details={"amount_credits": str(amount), "reason": reason, "balance": str(snapshot.credit_balance)},
        )
        return {"user_id": user_id, "credit_balance": str(snapshot.credit_balance)}

    async def list_models(self) -> list[dict]:
        policies_result = await self.session.execute(
            select(ModelPolicyModel).where(ModelPolicyModel.tenant_id == self.tenant_id)
        )
        policies = {item.model_id: item for item in policies_result.scalars().all()}
        codex_config = load_codex_model_config(Path.cwd())
        values = []
        for base in default_model_catalog().values():
            policy = policies.get(base.id)
            runtime = resolve_model_runtime(base.id, codex_config=codex_config)
            input_price = Decimal(policy.input_usd_per_1m) if policy and policy.input_usd_per_1m else base.input_usd_per_1m
            output_price = Decimal(policy.output_usd_per_1m) if policy and policy.output_usd_per_1m else base.output_usd_per_1m
            values.append({
                "id": base.id,
                "provider": base.provider,
                "display_name": base.display_name,
                "category": base.category,
                "enabled": policy.enabled if policy else base.enabled,
                "is_default": bool(policy and policy.is_default),
                "input_usd_per_1m": str(input_price),
                "output_usd_per_1m": str(output_price),
                "context_window": base.context_window,
                "credential_status": "configured" if runtime.api_key else "missing",
            })
        return values

    async def update_model(self, *, model_id: str, payload: dict) -> dict:
        if model_id not in default_model_catalog():
            raise LookupError("模型不存在。")
        result = await self.session.execute(
            select(ModelPolicyModel).where(
                ModelPolicyModel.tenant_id == self.tenant_id,
                ModelPolicyModel.model_id == model_id,
            )
        )
        policy = result.scalar_one_or_none()
        if payload["is_default"] and not payload["enabled"]:
            raise BillingError("默认模型必须处于启用状态。")
        if payload["is_default"]:
            other_rows = await self.session.execute(
                select(ModelPolicyModel).where(ModelPolicyModel.tenant_id == self.tenant_id)
            )
            for other in other_rows.scalars().all():
                other.is_default = False
        if policy is None:
            policy = ModelPolicyModel(tenant_id=self.tenant_id, model_id=model_id)
            self.session.add(policy)
        policy.enabled = payload["enabled"]
        policy.is_default = payload["is_default"]
        policy.input_usd_per_1m = str(payload["input_usd_per_1m"])
        policy.output_usd_per_1m = str(payload["output_usd_per_1m"])
        policy.updated_by = self.actor_id
        await self._audit("model_policy_updated", target=model_id, details=payload)
        return {"model_id": model_id, "updated": True}

    async def list_plans(self) -> list[dict]:
        await self._ensure_default_plans()
        result = await self.session.execute(
            select(SubscriptionPlanModel)
            .where(SubscriptionPlanModel.tenant_id == self.tenant_id)
            .order_by(SubscriptionPlanModel.sort_order, SubscriptionPlanModel.created_at)
        )
        return [self._plan_payload(plan) for plan in result.scalars().all()]

    async def get_enabled_plan(self, code: str) -> dict:
        await self._ensure_default_plans()
        result = await self.session.execute(
            select(SubscriptionPlanModel).where(
                SubscriptionPlanModel.tenant_id == self.tenant_id,
                SubscriptionPlanModel.code == code,
                SubscriptionPlanModel.enabled.is_(True),
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise LookupError("套餐不存在或已下架。")
        return self._plan_payload(plan)

    async def upsert_plan(self, payload: dict) -> dict:
        result = await self.session.execute(
            select(SubscriptionPlanModel).where(
                SubscriptionPlanModel.tenant_id == self.tenant_id,
                SubscriptionPlanModel.code == payload["code"],
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            plan = SubscriptionPlanModel(tenant_id=self.tenant_id, code=payload["code"])
            self.session.add(plan)
        plan.name = payload["name"].strip()
        plan.price_micros = credits_to_micros(payload["price_credits"])
        plan.credits_micros = credits_to_micros(payload["included_credits"])
        plan.duration_days = payload["duration_days"]
        plan.enabled = payload["enabled"]
        plan.sort_order = payload["sort_order"]
        plan.features_json = [str(item).strip()[:120] for item in payload["features"] if str(item).strip()]
        plan.updated_by = self.actor_id
        await self._audit("subscription_plan_updated", target=plan.code, details={"enabled": plan.enabled})
        await self.session.flush()
        return self._plan_payload(plan)

    async def list_orders(self, *, limit: int = 20, offset: int = 0) -> list[dict]:
        result = await self.session.execute(
            select(RechargeOrderModel)
            .where(RechargeOrderModel.tenant_id == self.tenant_id)
            .order_by(RechargeOrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [{
            "id": str(order.id),
            "user_id": order.user_id,
            "amount_credits": str(micros_to_credits(order.amount_micros)),
            "credited_amount": str(micros_to_credits(order.credit_amount_micros or order.amount_micros)),
            "status": order.status,
            "payment_provider": order.payment_provider,
            "external_order_id": order.external_order_id,
            "created_at": order.created_at.isoformat(),
        } for order in result.scalars().all()]

    async def list_audit(self, *, limit: int = 20, offset: int = 0) -> list[dict]:
        result = await self.session.execute(
            select(SecurityEventModel)
            .where(
                SecurityEventModel.tenant_id == self.tenant_id,
                SecurityEventModel.event_type.like("admin_%"),
            )
            .order_by(SecurityEventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [{
            "id": str(event.id),
            "actor_id": (event.metadata_json or {}).get("actor_id"),
            "action": event.event_type.removeprefix("admin_"),
            "target": (event.metadata_json or {}).get("target"),
            "details": (event.metadata_json or {}).get("details") or {},
            "created_at": event.created_at.isoformat(),
        } for event in result.scalars().all()]

    async def _ensure_default_plans(self) -> None:
        count = await self.session.scalar(
            select(func.count(SubscriptionPlanModel.id)).where(SubscriptionPlanModel.tenant_id == self.tenant_id)
        )
        if count:
            return
        defaults = [
            ("starter", "入门版", 19, 25, 30, ["模拟面试", "刷题与错题本"]),
            ("pro", "进阶版", 49, 80, 30, ["全部 Agent 能力", "个性化复习计划", "面试报告"]),
            ("intensive", "冲刺版", 99, 180, 90, ["全部 Agent 能力", "长期学习档案", "优先模型额度"]),
        ]
        for order, (code, name, price, credits, days, features) in enumerate(defaults):
            self.session.add(SubscriptionPlanModel(
                tenant_id=self.tenant_id,
                code=code,
                name=name,
                price_micros=credits_to_micros(price),
                credits_micros=credits_to_micros(credits),
                duration_days=days,
                enabled=True,
                sort_order=order,
                features_json=features,
                updated_by=self.actor_id,
            ))
        await self.session.flush()

    async def _require_account(self, user_id: str, *, for_update: bool = False) -> UserAccountModel:
        statement = select(UserAccountModel).where(
            UserAccountModel.tenant_id == self.tenant_id,
            UserAccountModel.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        account = result.scalar_one_or_none()
        if account is None:
            raise LookupError("用户不存在。")
        return account

    async def _audit(self, action: str, *, target: str, details: dict) -> None:
        await SecurityService(self.session, tenant_id=self.tenant_id).record_event(
            user_id=self.actor_id,
            event_type=f"admin_{action}",
            severity="warning",
            metadata={"actor_id": self.actor_id, "target": target, "details": _json_safe(details)},
        )

    @staticmethod
    def _user_payload(account: UserAccountModel, roles: list[str]) -> dict:
        return {
            "user_id": account.user_id,
            "display_name": account.display_name,
            "email": account.email,
            "platform": account.platform,
            "status": account.status,
            "roles": sorted(set(roles)),
            "trial_uses_remaining": account.trial_uses_remaining,
            "credit_balance": str(micros_to_credits(account.credit_balance_micros)),
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat(),
        }

    @staticmethod
    def _plan_payload(plan: SubscriptionPlanModel) -> dict:
        return {
            "id": str(plan.id),
            "code": plan.code,
            "name": plan.name,
            "price_credits": str(micros_to_credits(plan.price_micros)),
            "included_credits": str(micros_to_credits(plan.credits_micros)),
            "duration_days": plan.duration_days,
            "enabled": plan.enabled,
            "sort_order": plan.sort_order,
            "features": plan.features_json or [],
            "updated_at": plan.updated_at.isoformat(),
        }


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
