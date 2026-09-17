from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.routes.review_plans import (
    _repository,
    _require_authenticated,
    progress_to_response,
)
from interview_agent.interfaces.schemas import (
    ReviewCheckinRequest,
    ReviewProgressResponse,
    ReviewProgressUpdateRequest,
)
from interview_agent.services.achievement_service import safe_evaluate
from interview_agent.services.review_checkin_service import ReviewCheckinService


logger = logging.getLogger("interview_agent.api.review_progress")


def create_review_progress_router() -> APIRouter:
    router = APIRouter()

    @router.patch("/review-site/progress/task/{task_id}", response_model=ReviewProgressResponse)
    async def update_review_progress(
        task_id: str,
        request: ReviewProgressUpdateRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewProgressResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                progress = await _repository(db, context).update_progress(task_id, {
                    "done": request.done,
                    "note": request.note,
                    "elapsed_minutes": request.elapsed_minutes,
                    "mastery_score": request.mastery_score,
                })
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            try:
                await ReviewCheckinService(
                    db,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                ).sync_day_checkin(progress.plan_id, progress.day_id)
            except Exception:  # noqa: BLE001
                logger.exception("sync checkin after progress update failed")
            await safe_evaluate(db, tenant_id=context.tenant_id, user_id=context.user_id)
        return progress_to_response(progress)

    @router.get("/review-site/plans/{plan_id}/today")
    async def get_review_plan_today(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                return await ReviewCheckinService(
                    db,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                ).get_today(plan_id)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail="plan not found") from exc

    @router.post("/review-site/plans/{plan_id}/checkin")
    async def create_review_checkin(
        plan_id: str,
        request: ReviewCheckinRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            service = ReviewCheckinService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            try:
                result = await service.checkin(
                    plan_id,
                    elapsed_minutes=request.elapsed_minutes,
                    note=request.note,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail="plan not found") from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            await safe_evaluate(db, tenant_id=context.tenant_id, user_id=context.user_id)
            return result

    @router.get("/review-site/checkins")
    async def list_review_checkins(
        plan_id: str | None = Query(default=None, max_length=64),
        date_from: str | None = Query(default=None, max_length=10),
        date_to: str | None = Query(default=None, max_length=10),
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            return await ReviewCheckinService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_checkins(
                plan_id=plan_id,
                date_from=_parse_date(date_from),
                date_to=_parse_date(date_to),
            )

    return router


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD。") from None
