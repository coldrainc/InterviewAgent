from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.learning.today_service import LearningTodayService

router = APIRouter()


@router.get("/today")
async def get_learning_today(
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        return await LearningTodayService(
            db, tenant_id=context.tenant_id, user_id=context.user_id
        ).get_today()
