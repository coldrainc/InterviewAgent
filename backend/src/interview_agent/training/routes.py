from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.learning.routes.dependencies import require_authenticated
from interview_agent.training.drill_service import TrainingDrillService
from interview_agent.training.spaced_review_service import SpacedReviewService

router = APIRouter(prefix="/training", tags=["training"])


class DrillRequest(BaseModel):
    focus: str = Field(default="", max_length=128)
    count: int = Field(default=10, ge=1, le=50)
    difficulty: str | None = Field(default=None, pattern="^(easy|medium|hard)$")


class ReviewGradeRequest(BaseModel):
    quality: int = Field(ge=0, le=5)


@router.post("/drills")
async def create_drill(request: DrillRequest, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await TrainingDrillService(db, tenant_id=context.tenant_id, user_id=context.user_id).create(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drills/{drill_id}")
async def get_drill(drill_id: str, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await TrainingDrillService(db, tenant_id=context.tenant_id, user_id=context.user_id).get(drill_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="drill not found") from exc


@router.post("/drills/{drill_id}/complete")
async def complete_drill(drill_id: str, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await TrainingDrillService(db, tenant_id=context.tenant_id, user_id=context.user_id).complete(drill_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="drill not found") from exc


@router.post("/spaced-review/sync")
async def sync_spaced_review(context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        return await SpacedReviewService(db, tenant_id=context.tenant_id, user_id=context.user_id).sync_wrong_book()


@router.get("/spaced-review/due")
async def get_due_review(limit: int = 20, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        service = SpacedReviewService(db, tenant_id=context.tenant_id, user_id=context.user_id)
        await service.sync_wrong_book()
        return await service.due(limit=limit)


@router.post("/spaced-review/{item_id}/grade")
async def grade_review(item_id: str, request: ReviewGradeRequest, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await SpacedReviewService(db, tenant_id=context.tenant_id, user_id=context.user_id).grade(item_id, request.quality)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="review item not found") from exc
