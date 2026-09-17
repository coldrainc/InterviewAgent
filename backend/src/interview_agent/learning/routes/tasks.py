from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.command_service import LearningCommandService
from interview_agent.learning.errors import LearningConflictError, VersionConflictError
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.learning.schemas import LearningTaskCommandRequest
from interview_agent.services.achievement_service import safe_evaluate

router = APIRouter(prefix="/tasks")


@router.get("/{task_id}")
async def get_learning_task(
    task_id: str,
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await LearningCommandService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).task_view(task_id)
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc


@router.post("/{task_id}/commands")
async def execute_learning_task_command(
    task_id: str,
    request: LearningTaskCommandRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        service = LearningCommandService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        try:
            result = await service.execute(
                task_id,
                idempotency_key=idempotency_key,
                **request.model_dump(),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc
        except VersionConflictError as exc:
            current_task = await service.task_view(task_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": exc.code,
                    "message": str(exc),
                    "expected_version": exc.expected,
                    "current_version": exc.current,
                    "current_task": current_task,
                    "resolution": "refresh_and_retry",
                },
            ) from exc
        except LearningConflictError as exc:
            raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if result["receipt"]["accepted"] and not result["idempotent_replay"]:
            await safe_evaluate(db, tenant_id=context.tenant_id, user_id=context.user_id)
        return result
