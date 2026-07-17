from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.billing import (
    DEFAULT_TRIAL_USES,
    ModelPricing,
    TokenUsage,
    calculate_charge,
    credits_to_micros,
    default_model_catalog,
    estimate_tokens,
    get_model_pricing,
    micros_to_credits,
)
from interview_agent.infrastructure.db.models import (
    CreditLedgerModel,
    RechargeOrderModel,
    UsageRecordModel,
    UserAccountModel,
)


class BillingError(Exception):
    pass


class InsufficientCreditsError(BillingError):
    pass


@dataclass(frozen=True)
class AccountSnapshot:
    tenant_id: str
    user_id: str
    display_name: str
    email: str | None
    platform: str
    trial_uses_remaining: int
    credit_balance_micros: int

    @property
    def credit_balance(self) -> Decimal:
        return micros_to_credits(self.credit_balance_micros)


@dataclass(frozen=True)
class ChargeResult:
    account: AccountSnapshot
    model: ModelPricing
    usage: TokenUsage
    cost_credits_micros: int
    trial_used: bool


@dataclass(frozen=True)
class RechargeResult:
    account: AccountSnapshot
    created: bool


@dataclass(frozen=True)
class PaymentOrderResult:
    tenant_id: str
    user_id: str
    amount_micros: int
    payment_provider: str
    external_order_id: str
    status: str
    created: bool
    metadata: dict | None = None


class BillingService:
    def __init__(self, session: AsyncSession, *, trial_uses: int = DEFAULT_TRIAL_USES) -> None:
        self.session = session
        self.trial_uses = trial_uses

    async def register_with_password(
        self,
        *,
        tenant_id: str,
        email: str,
        password: str,
        display_name: str = "",
        platform: str = "web",
    ) -> UserAccountModel:
        normalized_email = _normalize_email(email)
        if len(password) < 8:
            raise BillingError("密码至少需要 8 位。")
        existing = await self._get_by_email(tenant_id, normalized_email)
        if existing is not None:
            raise BillingError("该邮箱已注册。")
        user_id = f"email:{normalized_email}"
        account = UserAccountModel(
            tenant_id=tenant_id,
            user_id=user_id,
            email=normalized_email,
            password_hash=_hash_password(password),
            display_name=display_name or normalized_email.split("@")[0],
            platform=platform,
            trial_uses_remaining=self.trial_uses,
            credit_balance_micros=0,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def authenticate_password(
        self,
        *,
        tenant_id: str,
        email: str,
        password: str,
    ) -> UserAccountModel | None:
        account = await self._get_by_email(tenant_id, _normalize_email(email))
        if account is None or account.password_hash is None:
            return None
        return account if _verify_password(password, account.password_hash) else None

    async def get_or_create_account(
        self,
        *,
        tenant_id: str,
        user_id: str,
        display_name: str = "",
        platform: str = "unknown",
        for_update: bool = False,
    ) -> UserAccountModel:
        account = await self._get_by_user_id(tenant_id, user_id, for_update=for_update)
        if account is not None:
            changed = False
            if display_name and account.display_name != display_name:
                account.display_name = display_name
                changed = True
            if platform and account.platform != platform:
                account.platform = platform
                changed = True
            if changed:
                await self.session.flush()
            return account
        account = UserAccountModel(
            tenant_id=tenant_id,
            user_id=user_id,
            display_name=display_name,
            platform=platform,
            trial_uses_remaining=self.trial_uses,
            credit_balance_micros=0,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def account_snapshot(self, *, tenant_id: str, user_id: str) -> AccountSnapshot:
        account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id)
        return _snapshot(account)

    async def recharge(
        self,
        *,
        tenant_id: str,
        user_id: str,
        amount_credits: Decimal | int | float | str,
        payment_provider: str = "mock",
        external_order_id: str | None = None,
        metadata: dict | None = None,
    ) -> AccountSnapshot:
        amount_micros = _amount_to_micros(amount_credits)
        account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id, for_update=True)
        order_id = external_order_id or f"manual-{uuid.uuid4()}"
        existing_order = await self.session.execute(
            select(RechargeOrderModel).where(
                RechargeOrderModel.tenant_id == tenant_id,
                RechargeOrderModel.external_order_id == order_id,
            )
        )
        if existing_order.scalar_one_or_none() is not None:
            raise BillingError("充值订单已存在。")
        account.credit_balance_micros += amount_micros
        self.session.add(
            RechargeOrderModel(
                account_id=account.id,
                tenant_id=tenant_id,
                user_id=user_id,
                amount_micros=amount_micros,
                payment_provider=payment_provider,
                external_order_id=order_id,
                metadata_json=metadata or {},
            )
        )
        self.session.add(
            CreditLedgerModel(
                account_id=account.id,
                tenant_id=tenant_id,
                user_id=user_id,
                kind="recharge",
                amount_micros=amount_micros,
                balance_after_micros=account.credit_balance_micros,
                external_order_id=order_id,
                metadata_json=metadata or {},
            )
        )
        await self.session.flush()
        return _snapshot(account)

    async def recharge_order_exists(self, *, tenant_id: str, external_order_id: str) -> bool:
        order_id = external_order_id.strip()
        if not order_id:
            return False
        result = await self.session.execute(
            select(RechargeOrderModel.id).where(
                RechargeOrderModel.tenant_id == tenant_id,
                RechargeOrderModel.external_order_id == order_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_payment_order(
        self,
        *,
        tenant_id: str,
        user_id: str,
        amount_credits: Decimal | int | float | str,
        payment_provider: str,
        external_order_id: str | None = None,
        metadata: dict | None = None,
    ) -> PaymentOrderResult:
        amount_micros = _amount_to_micros(amount_credits)
        provider = _clean_payment_provider(payment_provider)
        order_id = _clean_order_id(external_order_id) if external_order_id else f"order-{uuid.uuid4()}"
        existing = await self.session.execute(
            select(RechargeOrderModel).where(
                RechargeOrderModel.tenant_id == tenant_id,
                RechargeOrderModel.external_order_id == order_id,
            )
        )
        existing_order = existing.scalar_one_or_none()
        if existing_order is not None:
            if (
                existing_order.user_id != user_id
                or existing_order.amount_micros != amount_micros
                or existing_order.payment_provider != provider
            ):
                raise BillingError("支付订单已存在，但用户、金额或渠道不一致。")
            return PaymentOrderResult(
                tenant_id=tenant_id,
                user_id=user_id,
                amount_micros=existing_order.amount_micros,
                payment_provider=existing_order.payment_provider,
                external_order_id=existing_order.external_order_id,
                status=existing_order.status,
                created=False,
                metadata=existing_order.metadata_json or {},
            )
        account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id, for_update=True)
        self.session.add(
            RechargeOrderModel(
                account_id=account.id,
                tenant_id=tenant_id,
                user_id=user_id,
                amount_micros=amount_micros,
                status="pending",
                payment_provider=provider,
                external_order_id=order_id,
                metadata_json=metadata or {},
            )
        )
        await self.session.flush()
        return PaymentOrderResult(
            tenant_id=tenant_id,
            user_id=user_id,
            amount_micros=amount_micros,
            payment_provider=provider,
            external_order_id=order_id,
            status="pending",
            created=True,
            metadata=metadata or {},
        )

    async def get_payment_order(
        self,
        *,
        tenant_id: str,
        user_id: str,
        external_order_id: str,
    ) -> PaymentOrderResult | None:
        order_id = _clean_order_id(external_order_id)
        result = await self.session.execute(
            select(RechargeOrderModel).where(
                RechargeOrderModel.tenant_id == tenant_id,
                RechargeOrderModel.user_id == user_id,
                RechargeOrderModel.external_order_id == order_id,
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            return None
        return PaymentOrderResult(
            tenant_id=tenant_id,
            user_id=user_id,
            amount_micros=order.amount_micros,
            payment_provider=order.payment_provider,
            external_order_id=order.external_order_id,
            status=order.status,
            created=False,
            metadata=order.metadata_json or {},
        )

    async def find_payment_order_by_external_id(
        self,
        *,
        external_order_id: str,
    ) -> PaymentOrderResult | None:
        order_id = _clean_order_id(external_order_id)
        result = await self.session.execute(
            select(RechargeOrderModel).where(RechargeOrderModel.external_order_id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            return None
        return PaymentOrderResult(
            tenant_id=order.tenant_id,
            user_id=order.user_id,
            amount_micros=order.amount_micros,
            payment_provider=order.payment_provider,
            external_order_id=order.external_order_id,
            status=order.status,
            created=False,
            metadata=order.metadata_json or {},
        )

    async def update_payment_order_metadata(
        self,
        *,
        tenant_id: str,
        user_id: str,
        external_order_id: str,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> PaymentOrderResult:
        order_id = _clean_order_id(external_order_id)
        result = await self.session.execute(
            select(RechargeOrderModel)
            .where(
                RechargeOrderModel.tenant_id == tenant_id,
                RechargeOrderModel.user_id == user_id,
                RechargeOrderModel.external_order_id == order_id,
            )
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise BillingError("支付订单不存在。")
        if status:
            order.status = status
        order.metadata_json = {**(order.metadata_json or {}), **(metadata or {})}
        await self.session.flush()
        return PaymentOrderResult(
            tenant_id=tenant_id,
            user_id=user_id,
            amount_micros=order.amount_micros,
            payment_provider=order.payment_provider,
            external_order_id=order.external_order_id,
            status=order.status,
            created=False,
            metadata=order.metadata_json or {},
        )

    async def apply_paid_order(
        self,
        *,
        tenant_id: str,
        user_id: str,
        amount_credits: Decimal | int | float | str,
        payment_provider: str,
        external_order_id: str,
        metadata: dict | None = None,
    ) -> RechargeResult:
        if not external_order_id or len(external_order_id.strip()) > 128:
            raise BillingError("支付订单号无效。")
        order_id = _clean_order_id(external_order_id)
        provider = _clean_payment_provider(payment_provider)
        amount_micros = _amount_to_micros(amount_credits)
        statement = select(RechargeOrderModel).where(
            RechargeOrderModel.tenant_id == tenant_id,
            RechargeOrderModel.external_order_id == order_id,
        )
        existing = await self.session.execute(statement.with_for_update())
        existing_order = existing.scalar_one_or_none()
        if existing_order is not None:
            if existing_order.user_id != user_id or existing_order.amount_micros != amount_micros:
                raise BillingError("支付订单已存在，但用户或金额不一致。")
            account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id, for_update=True)
            if existing_order.status == "paid":
                return RechargeResult(account=_snapshot(account), created=False)
            if existing_order.status not in {"pending", "created"}:
                raise BillingError("支付订单状态不允许入账。")
            account.credit_balance_micros += amount_micros
            existing_order.status = "paid"
            existing_order.payment_provider = provider
            existing_order.metadata_json = {
                **(existing_order.metadata_json or {}),
                **(metadata or {}),
                "source": "payment_webhook",
            }
            self.session.add(
                CreditLedgerModel(
                    account_id=account.id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    kind="recharge",
                    amount_micros=amount_micros,
                    balance_after_micros=account.credit_balance_micros,
                    external_order_id=order_id,
                    metadata_json=existing_order.metadata_json,
                )
            )
            await self.session.flush()
            return RechargeResult(account=_snapshot(account), created=True)
        snapshot = await self.recharge(
            tenant_id=tenant_id,
            user_id=user_id,
            amount_credits=amount_credits,
            payment_provider=provider,
            external_order_id=order_id,
            metadata={**(metadata or {}), "source": "payment_webhook"},
        )
        return RechargeResult(account=snapshot, created=True)

    async def ensure_can_use(
        self,
        *,
        tenant_id: str,
        user_id: str,
        model_id: str,
    ) -> AccountSnapshot:
        account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id, for_update=True)
        model = get_model_pricing(model_id)
        minimum_micros = calculate_charge(model, TokenUsage(input_tokens=1, output_tokens=1))
        if account.trial_uses_remaining <= 0 and account.credit_balance_micros < minimum_micros:
            raise InsufficientCreditsError("试用次数已用完，积分余额不足，请先充值。")
        return _snapshot(account)

    async def record_generation_usage(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str | None,
        event_type: str,
        model_id: str,
        prompt_text: str,
        response_text: str,
        usage: TokenUsage | None = None,
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> ChargeResult:
        account = await self.get_or_create_account(tenant_id=tenant_id, user_id=user_id, for_update=True)
        model = get_model_pricing(model_id)
        if idempotency_key:
            existing = await self.session.execute(
                select(UsageRecordModel).where(
                    UsageRecordModel.tenant_id == tenant_id,
                    UsageRecordModel.idempotency_key == idempotency_key,
                )
            )
            existing_record = existing.scalar_one_or_none()
            if existing_record is not None:
                return ChargeResult(
                    account=_snapshot(account),
                    model=get_model_pricing(existing_record.model_id),
                    usage=TokenUsage(
                        input_tokens=existing_record.input_tokens,
                        output_tokens=existing_record.output_tokens,
                    ),
                    cost_credits_micros=existing_record.cost_credits_micros,
                    trial_used=existing_record.trial_used,
                )
        resolved_usage = usage or TokenUsage(
            input_tokens=estimate_tokens(prompt_text),
            output_tokens=estimate_tokens(response_text),
        )
        trial_used = False
        cost_micros = calculate_charge(model, resolved_usage)
        if account.trial_uses_remaining > 0:
            account.trial_uses_remaining -= 1
            charge_micros = 0
            trial_used = True
        else:
            charge_micros = cost_micros
            if account.credit_balance_micros < charge_micros:
                raise InsufficientCreditsError("积分余额不足，请先充值。")
            account.credit_balance_micros -= charge_micros
            self.session.add(
                CreditLedgerModel(
                    account_id=account.id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    kind="usage",
                    amount_micros=-charge_micros,
                    balance_after_micros=account.credit_balance_micros,
                    metadata_json={
                        "session_id": session_id,
                        "event_type": event_type,
                        "model_id": model.id,
                        **(metadata or {}),
                    },
                )
            )
        self.session.add(
            UsageRecordModel(
                account_id=account.id,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
                model_id=model.id,
                provider=model.provider,
                input_tokens=resolved_usage.input_tokens,
                output_tokens=resolved_usage.output_tokens,
                total_tokens=resolved_usage.total_tokens,
                cost_credits_micros=0 if trial_used else charge_micros,
                trial_used=trial_used,
                metadata_json={
                    "estimated": usage is None,
                    "list_price_cost_micros": cost_micros,
                    **(metadata or {}),
                },
            )
        )
        await self.session.flush()
        return ChargeResult(
            account=_snapshot(account),
            model=model,
            usage=resolved_usage,
            cost_credits_micros=0 if trial_used else charge_micros,
            trial_used=trial_used,
        )

    async def _get_by_user_id(
        self,
        tenant_id: str,
        user_id: str,
        *,
        for_update: bool = False,
    ) -> UserAccountModel | None:
        statement = select(UserAccountModel).where(
            UserAccountModel.tenant_id == tenant_id,
            UserAccountModel.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_by_email(self, tenant_id: str, email: str) -> UserAccountModel | None:
        result = await self.session.execute(
            select(UserAccountModel).where(
                UserAccountModel.tenant_id == tenant_id,
                UserAccountModel.email == email,
            )
        )
        return result.scalar_one_or_none()


def list_model_catalog() -> list[ModelPricing]:
    return [item for item in default_model_catalog().values() if item.enabled]


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or len(normalized) > 255:
        raise BillingError("邮箱格式无效。")
    return normalized


def validate_recharge_amount(amount: Decimal | int | float | str, max_credits: Decimal | str) -> None:
    value = _decimal_amount(amount)
    max_value = _decimal_amount(max_credits)
    if value <= 0:
        raise BillingError("充值积分必须大于 0。")
    if max_value > 0 and value > max_value:
        raise BillingError(f"单次充值不能超过 {max_value} 积分。")


def _amount_to_micros(amount: Decimal | int | float | str) -> int:
    value = _decimal_amount(amount)
    if value <= 0:
        raise BillingError("充值积分必须大于 0。")
    return credits_to_micros(value)


def _clean_payment_provider(value: str) -> str:
    provider = value.strip().lower()
    if not re.fullmatch(r"[a-zA-Z0-9_.:@-]{1,64}", provider):
        raise BillingError("支付渠道无效。")
    return provider


def _clean_order_id(value: str) -> str:
    order_id = value.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.:@/-]{1,128}", order_id):
        raise BillingError("支付订单号无效。")
    return order_id


def _decimal_amount(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BillingError("金额格式无效。") from exc
    if amount.as_tuple().exponent < -6:
        raise BillingError("金额最多支持 6 位小数。")
    return amount


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("ascii"),
            int(iterations),
        )
        return secrets.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def _snapshot(account: UserAccountModel) -> AccountSnapshot:
    return AccountSnapshot(
        tenant_id=account.tenant_id,
        user_id=account.user_id,
        display_name=account.display_name,
        email=account.email,
        platform=account.platform,
        trial_uses_remaining=account.trial_uses_remaining,
        credit_balance_micros=account.credit_balance_micros,
    )
