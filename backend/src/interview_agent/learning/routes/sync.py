from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.learning.sync_service import LearningSyncService


router = APIRouter()


@router.get("/sync")
async def pull_learning_changes(
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=100, ge=1, le=500),
    context: RequestContext = Depends(request_context),
) -> dict:
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await LearningSyncService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).pull(cursor=cursor, limit=limit)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_sync_cursor", "message": str(exc)},
            ) from exc
