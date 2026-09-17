from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AdminUserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")
    reason: str = Field(min_length=2, max_length=240)


class AdminBalanceAdjustmentRequest(BaseModel):
    amount_credits: Decimal
    reason: str = Field(min_length=2, max_length=240)


class AdminRoleRequest(BaseModel):
    role: str = Field(pattern="^(support|admin)$")
    reason: str = Field(min_length=2, max_length=240)


class AdminModelPolicyRequest(BaseModel):
    enabled: bool
    is_default: bool = False
    input_usd_per_1m: Decimal = Field(ge=0, le=10000)
    output_usd_per_1m: Decimal = Field(ge=0, le=10000)


class AdminPlanRequest(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    name: str = Field(min_length=2, max_length=128)
    price_credits: Decimal = Field(ge=0, le=1_000_000)
    included_credits: Decimal = Field(ge=0, le=10_000_000)
    duration_days: int = Field(ge=1, le=3660)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    features: list[str] = Field(default_factory=list, max_length=20)
