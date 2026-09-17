from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from interview_agent.domain.practice_grading import is_choice_question
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.routes.review_plans import _require_authenticated
from interview_agent.interfaces.schemas import (
    PracticeQuestionAttemptRequest,
    PracticeQuestionListResponse,
    PracticeQuestionMarkRequest,
    PracticeQuestionResponse,
)
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.services.achievement_service import safe_evaluate
from interview_agent.services.billing_service import InsufficientCreditsError
from interview_agent.services.practice_attempt_service import PracticeAttemptService


def create_review_practice_router(
    *,
    build_subjective_grader: Callable,
    billing_service_factory: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/review-site/practice-questions", response_model=PracticeQuestionListResponse)
    async def list_practice_questions(
        category: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
        question_type: str | None = Query(default=None, max_length=64),
        difficulty: str | None = Query(default=None, max_length=32),
        keyword: str | None = Query(default=None, max_length=128),
        limit: int = Query(default=30, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> PracticeQuestionListResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            items, total = await _repository(db, context).list_questions(
                category=category,
                subject=subject,
                question_type=question_type,
                difficulty=difficulty,
                keyword=keyword,
                limit=limit,
                offset=offset,
            )
        return PracticeQuestionListResponse(
            items=[PracticeQuestionResponse(**item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
            next_offset=offset + len(items) if offset + len(items) < total else None,
        )

    @router.post("/review-site/practice-questions/{question_id}/mark")
    async def mark_practice_question(
        question_id: str,
        request: PracticeQuestionMarkRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                return await _repository(db, context).update_wrong_entry(question_id, {
                    "mark_type": request.mark_type,
                    "mastery_level": request.mastery_level,
                    "note": request.note,
                })
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/review-site/practice-questions/{question_id}/attempt")
    async def submit_practice_question_attempt(
        question_id: str,
        request: PracticeQuestionAttemptRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            question = await _repository(db, context).get_question(question_id)
            if question is None:
                raise HTTPException(status_code=404, detail="题目不存在。")
            subjective_grader = None
            model_id = ""
            if request.answer.strip() and not is_choice_question(question):
                subjective_grader, model_id = build_subjective_grader()
                if subjective_grader is not None:
                    try:
                        await billing_service_factory(db).ensure_can_use(
                            tenant_id=context.tenant_id,
                            user_id=context.user_id,
                            model_id=model_id,
                        )
                    except InsufficientCreditsError as exc:
                        raise HTTPException(status_code=402, detail=str(exc)) from exc
            service = PracticeAttemptService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                subjective_grader=subjective_grader,
            )
            try:
                result = await service.submit_attempt(
                    question_id=question_id,
                    answer=request.answer,
                    elapsed_seconds=request.elapsed_seconds,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail="题目不存在。") from exc
            if subjective_grader is not None and result.get("graded_by") == "llm":
                try:
                    await billing_service_factory(db).record_generation_usage(
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                        session_id=None,
                        event_type="practice_grade",
                        model_id=model_id,
                        prompt_text=request.answer[:4000],
                        response_text=str(result.get("feedback") or "")[:2000],
                    )
                except InsufficientCreditsError:
                    pass
            await safe_evaluate(db, tenant_id=context.tenant_id, user_id=context.user_id)
            return result

    @router.get("/review-site/practice-questions/{question_id}/attempts")
    async def list_practice_question_attempts(
        question_id: str,
        limit: int = Query(default=20, ge=1, le=100),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        async with session_scope() as db:
            return await _repository(db, context).list_attempts(question_id=question_id, limit=limit)

    @router.get("/review-site/wrong-book")
    async def list_wrong_book(
        mark_type: str | None = Query(default=None, max_length=32),
        mastery_max: int | None = Query(default=None, ge=0, le=5),
        category: str | None = Query(default=None, max_length=64),
        keyword: str | None = Query(default=None, max_length=128),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        async with session_scope() as db:
            return await _repository(db, context).list_wrong_book(
                mark_type=mark_type,
                mastery_max=mastery_max,
                category=category,
                keyword=keyword,
                limit=limit,
                offset=offset,
            )

    return router


def _repository(db, context: RequestContext) -> PracticeQuestionRepository:
    return PracticeQuestionRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
