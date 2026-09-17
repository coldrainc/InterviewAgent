from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.infrastructure.object_storage import ObjectStorage
from interview_agent.privacy.deletion_service import DataDeletionService
from interview_agent.privacy.export_service import UserDataExportService


class DeletionRequest(BaseModel):
    confirmation: str = Field(pattern="^DELETE$")
    reason: str = Field(default="", max_length=2000)


def create_privacy_router(*, object_storage: ObjectStorage) -> APIRouter:
    router = APIRouter(prefix="/privacy", tags=["privacy"])

    @router.get("/export")
    async def export_user_data(context: RequestContext = Depends(request_context)) -> dict:
        require_authenticated(context)
        async with session_scope() as db:
            return await UserDataExportService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).export()

    @router.get("/deletion")
    async def get_deletion(context: RequestContext = Depends(request_context)) -> dict:
        require_authenticated(context)
        async with session_scope() as db:
            request = await DataDeletionService(
                db, tenant_id=context.tenant_id, user_id=context.user_id, object_storage=object_storage
            ).current()
        return {"request": request, "cooling_off_days": 7}

    @router.post("/deletion")
    async def schedule_deletion(
        request: DeletionRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        require_authenticated(context)
        async with session_scope() as db:
            return await DataDeletionService(
                db, tenant_id=context.tenant_id, user_id=context.user_id, object_storage=object_storage
            ).schedule(reason=request.reason)

    @router.delete("/deletion")
    async def cancel_deletion(context: RequestContext = Depends(request_context)) -> dict:
        require_authenticated(context)
        async with session_scope() as db:
            try:
                return await DataDeletionService(
                    db, tenant_id=context.tenant_id, user_id=context.user_id, object_storage=object_storage
                ).cancel()
            except LookupError as exc:
                raise HTTPException(status_code=404, detail="no scheduled deletion request") from exc

    return router
