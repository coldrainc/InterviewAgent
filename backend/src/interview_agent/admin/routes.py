from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from interview_agent.admin.schemas import (
    AdminBalanceAdjustmentRequest,
    AdminModelPolicyRequest,
    AdminPlanRequest,
    AdminRoleRequest,
    AdminUserStatusRequest,
)
from interview_agent.admin.service import AdminConsoleService
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.services.billing_service import BillingError
from interview_agent.services.security_service import SecurityService


def create_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"])

    @router.get("/dashboard")
    async def dashboard(context: RequestContext = Depends(request_context)) -> dict:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).dashboard()

    @router.get("/users")
    async def users(
        query: str = Query(default="", max_length=128),
        status: str = Query(default="", max_length=32),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).list_users(query=query, status=status, limit=limit, offset=offset)

    @router.patch("/users/{user_id}/status")
    async def update_user_status(
        user_id: str,
        request: AdminUserStatusRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        async with session_scope() as db:
            try:
                return await _service(db, context).set_user_status(
                    user_id=user_id, status=request.status, reason=request.reason
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except BillingError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/users/{user_id}/balance-adjustments")
    async def adjust_user_balance(
        user_id: str,
        request: AdminBalanceAdjustmentRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        async with session_scope() as db:
            try:
                return await _service(db, context).adjust_balance(
                    user_id=user_id, amount=request.amount_credits, reason=request.reason
                )
            except BillingError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/users/{user_id}/roles")
    async def grant_role(
        user_id: str,
        request: AdminRoleRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        async with session_scope() as db:
            security = SecurityService(db, tenant_id=context.tenant_id)
            await security.grant_role(
                user_id=user_id,
                role=request.role,
                granted_by=context.user_id,
                metadata={"reason": request.reason, "source": "admin_console"},
            )
            await security.record_event(
                user_id=context.user_id,
                event_type="admin_user_role_granted",
                severity="warning",
                metadata={
                    "actor_id": context.user_id,
                    "target": user_id,
                    "details": {"role": request.role, "reason": request.reason},
                },
            )
            return {"updated": True}

    @router.delete("/users/{user_id}/roles/{role}")
    async def revoke_role(
        user_id: str,
        role: str,
        reason: str = Query(min_length=2, max_length=240),
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        if user_id == context.user_id and role == "admin":
            raise HTTPException(status_code=400, detail="不能移除当前登录账号的管理员角色。")
        async with session_scope() as db:
            revoked = await SecurityService(db, tenant_id=context.tenant_id).revoke_role(
                user_id=user_id, role=role, revoked_by=context.user_id
            )
            if revoked:
                await SecurityService(db, tenant_id=context.tenant_id).record_event(
                    user_id=context.user_id,
                    event_type="admin_user_role_revoked",
                    severity="warning",
                    metadata={"actor_id": context.user_id, "target": user_id, "details": {"role": role, "reason": reason}},
                )
            return {"updated": revoked}

    @router.get("/models")
    async def models(context: RequestContext = Depends(request_context)) -> list[dict]:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).list_models()

    @router.put("/models/{model_id}")
    async def update_model(
        model_id: str,
        request: AdminModelPolicyRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        async with session_scope() as db:
            try:
                return await _service(db, context).update_model(model_id=model_id, payload=request.model_dump())
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except BillingError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/plans")
    async def plans(context: RequestContext = Depends(request_context)) -> list[dict]:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).list_plans()

    @router.put("/plans/{plan_code}")
    async def update_plan(
        plan_code: str,
        request: AdminPlanRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_admin(context)
        if plan_code != request.code:
            raise HTTPException(status_code=400, detail="套餐编码不能修改。")
        async with session_scope() as db:
            return await _service(db, context).upsert_plan(request.model_dump())

    @router.get("/orders")
    async def orders(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).list_orders(limit=limit, offset=offset)

    @router.get("/audit")
    async def audit(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_admin(context)
        async with session_scope() as db:
            return await _service(db, context).list_audit(limit=limit, offset=offset)

    return router


def _service(db, context: RequestContext) -> AdminConsoleService:
    return AdminConsoleService(db, tenant_id=context.tenant_id, actor_id=context.user_id)


def _require_admin(context: RequestContext) -> None:
    if not context.authenticated:
        raise HTTPException(status_code=401, detail="请先登录后再继续。")
    if context.role not in {"admin", "server"}:
        raise HTTPException(status_code=403, detail="只有管理员可以访问管理后台。")
