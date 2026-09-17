from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.ability_service import AbilitySnapshotService
from interview_agent.learning.errors import VersionConflictError
from interview_agent.learning.goal_service import GoalService
from interview_agent.learning.revision_service import RevisionService
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.learning.schemas import LearningGoalRequest, RevisionDecisionRequest

router = APIRouter()


@router.get("/goals")
async def list_goals(context: RequestContext = Depends(request_context)) -> list[dict[str, Any]]:
    require_authenticated(context)
    async with session_scope() as db:
        return await GoalService(db, tenant_id=context.tenant_id, user_id=context.user_id).list()


@router.put("/goals/active")
async def put_active_goal(
    request: LearningGoalRequest,
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await GoalService(db, tenant_id=context.tenant_id, user_id=context.user_id).upsert(
                request.model_dump()
            )
        except VersionConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "expected_version": exc.expected, "current_version": exc.current},
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ability-snapshot")
async def get_ability_snapshot(
    refresh: bool = False,
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        goals = GoalService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        service = AbilitySnapshotService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        existing = None if refresh else await service.latest()
        if existing:
            return existing
        goal = await goals.active()
        return await service.compute(goal_id=goal["id"] if goal else None)


@router.post("/plans/{plan_id}/revisions/propose")
async def propose_revision(
    plan_id: str,
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        goals = GoalService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        goal = await goals.active()
        abilities = AbilitySnapshotService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        snapshot = await abilities.latest() or await abilities.compute(goal_id=goal["id"] if goal else None)
        try:
            revision = await RevisionService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).propose(
                plan_id,
                daily_minutes=int((goal or {}).get("daily_minutes") or 30),
                dimensions=snapshot["dimensions"],
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="plan not found") from exc
        return {"revision": revision, "changed": revision is not None}


@router.get("/plans/{plan_id}/revisions")
async def list_revisions(
    plan_id: str,
    context: RequestContext = Depends(request_context),
) -> list[dict[str, Any]]:
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await RevisionService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).list(plan_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="plan not found") from exc


@router.post("/revisions/{revision_id}/decision")
async def decide_revision(
    revision_id: str,
    request: RevisionDecisionRequest,
    context: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await RevisionService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).decide(revision_id, request.action)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="revision not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
