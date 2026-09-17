from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from interview_agent.core.industry import industry_options
from interview_agent.domain.civil_service import (
    CIVIL_SERVICE_SEED_QUESTIONS,
    DEFAULT_PRACTICE_QUESTIONS,
    PRACTICE_CATEGORIES,
    PRACTICE_LEARNING_PLAN,
)
from interview_agent.infrastructure.codex_config import load_codex_model_config
from interview_agent.infrastructure.content_security import scan_prompt_injection
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.model_runtime import (
    is_openai_compatible_provider,
    is_supported_native_provider,
    resolve_model_runtime,
)
from interview_agent.infrastructure.security import (
    RequestContext,
    authenticate_request,
    request_context,
)
from interview_agent.infrastructure.settings import load_settings
from interview_agent.interfaces.schemas import (
    CivilServiceQuestionImportRequest,
    CivilServiceQuestionListResponse,
    ImportResultResponse,
    IndustryOptionResponse,
    ModelOptionResponse,
    PracticeAttemptRequest,
    PracticeAttemptResponse,
)
from interview_agent.repositories.civil_service_repository import CivilServiceQuestionRepository
from interview_agent.services.billing_service import list_model_catalog_for_tenant
from interview_agent.services.civil_service_migration import map_civil_question
from interview_agent.services.security_service import SecurityService
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.admin.service import AdminConsoleService


def create_catalog_router(*, settings) -> APIRouter:
    router = APIRouter()

    @router.get("/metadata/models", response_model=list[ModelOptionResponse])
    async def models(
        context: RequestContext = Depends(_optional_catalog_context),
    ) -> list[ModelOptionResponse]:
        codex_model_config = load_codex_model_config(Path.cwd())
        responses: list[ModelOptionResponse] = []
        async with session_scope() as db:
            catalog = await list_model_catalog_for_tenant(db, context.tenant_id)
        for item in catalog:
            runtime = resolve_model_runtime(item.id, codex_config=codex_model_config)
            responses.append(
                ModelOptionResponse(
                    id=item.id,
                    provider=item.provider,
                    display_name=item.display_name,
                    category=item.category,
                    runtime_supported=(
                        is_openai_compatible_provider(runtime.provider)
                        or is_supported_native_provider(runtime.provider)
                    ),
                    runtime_integration=runtime.integration,
                    input_credits_per_1m=str(item.input_credits_per_1m),
                    output_credits_per_1m=str(item.output_credits_per_1m),
                    input_usd_per_1m=str(item.input_usd_per_1m),
                    output_usd_per_1m=str(item.output_usd_per_1m),
                    context_window=item.context_window,
                    notes=item.notes,
                )
            )
        return responses

    @router.get("/metadata/industries", response_model=list[IndustryOptionResponse])
    async def industries(
        target_role: str = Query(default="AI 应用工程师", min_length=1, max_length=80),
    ) -> list[IndustryOptionResponse]:
        return [IndustryOptionResponse(**item) for item in industry_options(target_role.strip())]

    @router.get("/billing/plans")
    async def billing_plans(
        context: RequestContext = Depends(_optional_catalog_context),
    ) -> list[dict]:
        async with session_scope() as db:
            plans = await AdminConsoleService(
                db,
                tenant_id=context.tenant_id,
                actor_id="system",
            ).list_plans()
        return [plan for plan in plans if plan["enabled"]]

    async def practice_learning_plan_impl(context: RequestContext) -> list[dict]:
        _require_authenticated(context)
        return PRACTICE_LEARNING_PLAN

    @router.get("/practice/learning-plan")
    async def practice_learning_plan(
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        return await practice_learning_plan_impl(context)

    @router.get("/civil-service/learning-plan")
    async def civil_service_learning_plan(
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        return await practice_learning_plan_impl(context)

    @router.get("/practice/categories")
    async def practice_categories(
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_authenticated(context)
        return PRACTICE_CATEGORIES

    async def list_questions_impl(
        category: str | None,
        year: int | None,
        subject: str | None,
        question_type: str | None,
        limit: int,
        offset: int,
        context: RequestContext,
    ) -> CivilServiceQuestionListResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            items, total = await CivilServiceQuestionRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_questions(
                category=category,
                year=year,
                subject=subject,
                question_type=question_type,
                limit=limit,
                offset=offset,
            )
        has_more = offset + len(items) < total
        return CivilServiceQuestionListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=offset + len(items) if has_more else None,
        )

    @router.get("/practice/questions", response_model=CivilServiceQuestionListResponse)
    async def list_practice_questions(
        category: str | None = Query(default=None, max_length=64),
        year: int | None = Query(default=None, ge=1990, le=2100),
        subject: str | None = Query(default=None, max_length=64),
        question_type: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=30, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> CivilServiceQuestionListResponse:
        return await list_questions_impl(category, year, subject, question_type, limit, offset, context)

    @router.get("/civil-service/questions", response_model=CivilServiceQuestionListResponse)
    async def list_civil_service_questions(
        year: int | None = Query(default=None, ge=1990, le=2100),
        subject: str | None = Query(default=None, max_length=64),
        question_type: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=30, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> CivilServiceQuestionListResponse:
        return await list_questions_impl("civil_service", year, subject, question_type, limit, offset, context)

    @router.post("/practice/attempt", response_model=PracticeAttemptResponse)
    async def submit_practice_attempt(
        request: PracticeAttemptRequest,
        context: RequestContext = Depends(request_context),
    ) -> PracticeAttemptResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            question = await CivilServiceQuestionRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get_question(request.question_id)
        if question is None:
            raise HTTPException(status_code=404, detail="题目不存在。")
        return PracticeAttemptResponse(
            question_id=request.question_id,
            elapsed_seconds=request.elapsed_seconds,
            **grade_practice_attempt(question, request.answer),
        )

    async def import_questions_impl(
        request: CivilServiceQuestionImportRequest,
        context: RequestContext,
    ) -> ImportResultResponse:
        _require_authenticated(context)
        if len(request.questions) > 500:
            raise HTTPException(status_code=413, detail="单次最多导入 500 道题。")
        suspicious_questions = []
        for index, question in enumerate(request.questions):
            prompt_text = str(question.get("prompt") or question.get("question") or "")
            scan = scan_prompt_injection(
                prompt_text,
                block_score=settings.prompt_injection_block_score,
                enabled=settings.prompt_injection_block_enabled,
            )
            if scan.blocked:
                suspicious_questions.append({"index": index, "score": scan.score})
        if suspicious_questions:
            async with session_scope() as db:
                await SecurityService(db, tenant_id=context.tenant_id).record_event(
                    user_id=context.user_id,
                    event_type="question_bank_prompt_injection_blocked",
                    severity="critical",
                    request_id=context.request_id,
                    metadata={"questions": suspicious_questions[:20]},
                )
            raise HTTPException(status_code=400, detail="题库包含疑似 Prompt Injection 内容，已拒绝导入。")
        async with session_scope() as db:
            try:
                result = await CivilServiceQuestionRepository(
                    db,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                ).upsert_many(request.questions)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ImportResultResponse(**result)

    @router.post("/practice/questions/import", response_model=ImportResultResponse)
    async def import_practice_questions(
        request: CivilServiceQuestionImportRequest,
        context: RequestContext = Depends(request_context),
    ) -> ImportResultResponse:
        return await import_questions_impl(request, context)

    @router.post("/civil-service/questions/import", response_model=ImportResultResponse)
    async def import_civil_service_questions(
        request: CivilServiceQuestionImportRequest,
        context: RequestContext = Depends(request_context),
    ) -> ImportResultResponse:
        for question in request.questions:
            question.setdefault("practice_category", "civil_service")
        return await import_questions_impl(request, context)

    async def seed_questions_impl(questions: list[dict], context: RequestContext) -> ImportResultResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            legacy_result = await CivilServiceQuestionRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).upsert_many(questions)
            result = await PracticeQuestionRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).bulk_upsert([map_civil_question(question) for question in questions])
        return ImportResultResponse(
            created=max(legacy_result["created"], result["created"]),
            updated=max(legacy_result["updated"], result["updated"]),
            total=max(legacy_result["total"], result["total"]),
        )

    @router.post("/practice/questions/seed", response_model=ImportResultResponse)
    async def seed_practice_questions(
        context: RequestContext = Depends(request_context),
    ) -> ImportResultResponse:
        return await seed_questions_impl(DEFAULT_PRACTICE_QUESTIONS, context)

    @router.post("/civil-service/questions/seed", response_model=ImportResultResponse)
    async def seed_civil_service_questions(
        context: RequestContext = Depends(request_context),
    ) -> ImportResultResponse:
        return await seed_questions_impl(CIVIL_SERVICE_SEED_QUESTIONS, context)

    return router


def _require_authenticated(context: RequestContext) -> None:
    if not context.authenticated or context.user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="请先登录后再继续。",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _optional_catalog_context(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> RequestContext:
    settings = load_settings()
    if authorization or x_api_key:
        return authenticate_request(settings, authorization=authorization, x_api_key=x_api_key)
    return RequestContext(
        tenant_id=settings.default_tenant_id,
        authenticated=False,
    )


def grade_practice_attempt(question: dict, user_answer: str) -> dict:
    answer = (user_answer or "").strip()
    reference_answer = str(question.get("answer") or "").strip()
    explanation = str(question.get("explanation") or "").strip()
    choices = question.get("choices") if isinstance(question.get("choices"), list) else []
    if not answer:
        return {
            "correct": False if reference_answer else None,
            "score": 0,
            "feedback": "还没有作答，先写出你的判断或答题思路。",
            "reference_answer": reference_answer or "开放题",
            "explanation": explanation or "暂无解析。",
            "suggestions": ["先给结论", "补充关键依据", "对照解析复盘遗漏点"],
        }
    if choices and reference_answer:
        correct = _normalize_choice_answer(answer) == _normalize_choice_answer(reference_answer)
        return {
            "correct": correct,
            "score": 100 if correct else 0,
            "feedback": "回答正确。" if correct else "答案不一致，建议回看题干限定条件和选项差异。",
            "reference_answer": reference_answer,
            "explanation": explanation or "暂无解析。",
            "suggestions": ["定位题干关键词", "排除绝对化或偷换概念选项", "复做同题型 2-3 道巩固方法"],
        }
    reference_text = " ".join(part for part in [reference_answer, explanation] if part)
    overlap = _keyword_overlap(answer, reference_text)
    score = min(100, max(20, int(overlap * 100))) if reference_text else 60
    feedback = (
        "要点覆盖较充分，可以继续优化表达结构和案例证据。"
        if score >= 75
        else "覆盖了部分要点，但还需要补足关键步骤、指标或依据。"
        if score >= 45
        else "回答和参考要点重合较少，建议先按结论、依据、步骤、风险重新组织。"
    )
    return {
        "correct": None,
        "score": score,
        "feedback": feedback,
        "reference_answer": reference_answer or "开放题",
        "explanation": explanation or "暂无解析。",
        "suggestions": ["先讲结论，再讲依据", "补充具体步骤或项目例子", "复盘遗漏关键词并重答一次"],
    }


def _normalize_choice_answer(value: str) -> str:
    cleaned = value.strip().upper()
    match = re.search(r"[A-D]", cleaned)
    return match.group(0) if match else cleaned


def _keyword_overlap(answer: str, reference: str) -> float:
    answer_terms = _practice_terms(answer)
    reference_terms = _practice_terms(reference)
    if not reference_terms:
        return 0.6
    return len(answer_terms & reference_terms) / len(reference_terms)


def _practice_terms(text: str) -> set[str]:
    lowered = text.lower()
    ascii_terms = set(re.findall(r"[a-z0-9_+#.-]{2,}", lowered))
    chinese_terms = set(re.findall(r"[\u4e00-\u9fff]{2,6}", lowered))
    stopwords = {"需要", "可以", "进行", "说明", "回答", "问题", "建议", "重点", "通过", "结合"}
    return {term for term in ascii_terms | chinese_terms if term not in stopwords}
