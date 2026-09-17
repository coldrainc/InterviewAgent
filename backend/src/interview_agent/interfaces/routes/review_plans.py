from __future__ import annotations

import copy
import time
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.schemas import (
    ReviewDayResponse,
    ReviewDayUpsertRequest,
    ReviewPhaseResponse,
    ReviewPlanCreateRequest,
    ReviewPlanListItem,
    ReviewPlanResponse,
    ReviewProgressResponse,
    ReviewTaskResponse,
    ReviewTaskUpsertRequest,
)
from interview_agent.repositories.review_site_repository import ReviewSiteRepository


def create_review_plans_router() -> APIRouter:
    router = APIRouter()

    @router.get("/review-site/plans", response_model=list[ReviewPlanListItem])
    async def list_review_plans(
        include_archived: bool = Query(default=False),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[ReviewPlanListItem]:
        _require_authenticated(context)
        async with session_scope() as db:
            plans = await _repository(db, context).list_plans(
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
        return [
            ReviewPlanListItem(
                id=str(plan.id),
                plan_key=plan.plan_key,
                title=plan.title,
                subtitle=plan.subtitle,
                status=plan.status,
                created_at=plan.created_at.isoformat() if plan.created_at else None,
                updated_at=plan.updated_at.isoformat() if plan.updated_at else None,
            )
            for plan in plans
        ]

    @router.post("/review-site/plans", response_model=ReviewPlanResponse)
    async def create_review_plan(
        request: ReviewPlanCreateRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewPlanResponse:
        _require_authenticated(context)
        plan_key = (request.plan_key or "").strip() or f"plan-{int(time.time())}"
        title = (request.title or "").strip() or "面试复习计划"
        async with session_scope() as db:
            repo = _repository(db, context)
            existing = await repo.get_plan_by_key(plan_key) if plan_key else None
            if existing:
                plan = existing
            else:
                plan = await repo.create_plan(
                    plan_data={"plan_key": plan_key, "title": title, "status": "draft"},
                    phases=[],
                    days=[],
                    tasks_per_day={},
                    intro_scripts=[],
                    star_cards=[],
                    a4_memory=[],
                )
            full_plan = await repo.get_plan(plan.id)
        return review_plan_to_response(full_plan) if full_plan else ReviewPlanResponse(id=str(plan.id))

    @router.get("/review-site/plans/{plan_id}", response_model=ReviewPlanResponse)
    async def get_review_plan(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> ReviewPlanResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            plan = await _repository(db, context).get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="plan not found")
        return review_plan_to_response(plan)

    @router.patch("/review-site/plans/{plan_id}", response_model=ReviewPlanResponse)
    async def update_review_plan(
        plan_id: str,
        payload: dict,
        context: RequestContext = Depends(request_context),
    ) -> ReviewPlanResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            repo = _repository(db, context)
            updated = await repo.update_plan(plan_id, payload)
            if not updated:
                raise HTTPException(status_code=404, detail="plan not found")
            plan = await repo.get_plan(plan_id)
        return review_plan_to_response(plan) if plan else ReviewPlanResponse(id=str(updated.id))

    @router.post("/review-site/plans/{plan_id}/archive", response_model=ReviewPlanResponse)
    async def archive_review_plan(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> ReviewPlanResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            repo = _repository(db, context)
            archived = await repo.archive_plan(plan_id)
            if not archived:
                raise HTTPException(status_code=404, detail="plan not found")
            plan = await repo.get_plan(plan_id)
        return review_plan_to_response(plan) if plan else ReviewPlanResponse(id=str(archived.id), status="archived")

    @router.post("/review-site/plans/{plan_id}/days", response_model=ReviewDayResponse, status_code=201)
    async def create_review_day(
        plan_id: str,
        request: ReviewDayUpsertRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewDayResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                day = await _repository(db, context).create_day(plan_id, request.model_dump(exclude_none=True))
            except ValueError:
                raise HTTPException(status_code=404, detail="plan not found") from None
            if day is None:
                raise HTTPException(status_code=404, detail="plan not found")
            return day_to_response(day)

    @router.patch("/review-site/days/{day_id}", response_model=ReviewDayResponse)
    async def update_review_day(
        day_id: str,
        request: ReviewDayUpsertRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewDayResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                day = await _repository(db, context).update_day(day_id, request.model_dump(exclude_none=True))
            except ValueError:
                day = None
            if day is None:
                raise HTTPException(status_code=404, detail="day not found")
            return day_to_response(day)

    @router.delete("/review-site/days/{day_id}")
    async def delete_review_day(
        day_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                deleted = await _repository(db, context).delete_day(day_id)
            except ValueError:
                deleted = False
            if not deleted:
                raise HTTPException(status_code=404, detail="day not found")
        return {"deleted": True}

    @router.post("/review-site/days/{day_id}/tasks", response_model=ReviewTaskResponse, status_code=201)
    async def create_review_task(
        day_id: str,
        request: ReviewTaskUpsertRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewTaskResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                task = await _repository(db, context).create_task(day_id, request.model_dump(exclude_none=True))
            except ValueError:
                task = None
            if task is None:
                raise HTTPException(status_code=404, detail="day not found")
            return task_to_response(task)

    @router.patch("/review-site/tasks/{task_id}", response_model=ReviewTaskResponse)
    async def update_review_task(
        task_id: str,
        request: ReviewTaskUpsertRequest,
        context: RequestContext = Depends(request_context),
    ) -> ReviewTaskResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                task = await _repository(db, context).update_task(task_id, request.model_dump(exclude_none=True))
            except ValueError:
                task = None
            if task is None:
                raise HTTPException(status_code=404, detail="task not found")
            return task_to_response(task)

    @router.delete("/review-site/tasks/{task_id}")
    async def delete_review_task(
        task_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            try:
                deleted = await _repository(db, context).delete_task(task_id)
            except ValueError:
                deleted = False
            if not deleted:
                raise HTTPException(status_code=404, detail="task not found")
        return {"deleted": True}

    return router


def _repository(db, context: RequestContext) -> ReviewSiteRepository:
    return ReviewSiteRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)


def _require_authenticated(context: RequestContext) -> None:
    if not context.authenticated or context.user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="请先登录后再继续。",
            headers={"WWW-Authenticate": "Bearer"},
        )


def task_to_response(task) -> ReviewTaskResponse:
    link_payload = _public_link_payload(task.link_payload_json or {})
    return ReviewTaskResponse(
        id=str(task.id),
        task_key=task.task_key,
        title=task.title,
        tags=list(task.tags_json or []),
        critical=bool(task.critical),
        simulation=bool(task.simulation),
        docs=_public_docs(task.docs_json or [], link_payload),
        reason=task.reason,
        source=task.source or "plan",
        link_type=task.link_type or "none",
        link_payload=link_payload,
        sort_order=task.sort_order,
    )


def _public_docs(docs_json, link_payload: dict) -> list:
    docs = list(docs_json or [])
    detail = link_payload.get("detail") if isinstance(link_payload, dict) else {}
    materials = detail.get("materials") if isinstance(detail, dict) else []
    if not docs and isinstance(materials, list):
        return [
            {
                "label": str(item.get("label") or f"资料 {index + 1}"),
                "source_index": index,
                "page_url": f"/review-site/materials/{index}",
            }
            for index, item in enumerate(materials)
            if isinstance(item, dict)
        ]

    public_docs = []
    for index, doc in enumerate(docs):
        if isinstance(doc, str):
            label = f"资料 {index + 1}"
            raw_url = doc
        elif isinstance(doc, dict):
            label = str(doc.get("label") or doc.get("title") or f"资料 {index + 1}")
            raw_url = str(doc.get("url") or doc.get("link") or doc.get("path") or "")
        else:
            continue

        if _is_public_http_url(raw_url):
            public_docs.append({"label": label, "url": raw_url})
        else:
            public_docs.append({
                "label": label,
                "source_index": index,
                "page_url": f"/review-site/materials/{index}",
            })
    return public_docs


def _public_link_payload(link_payload_json) -> dict:
    payload = copy.deepcopy(dict(link_payload_json or {}))
    detail = payload.get("detail")
    if not isinstance(detail, dict):
        return payload
    materials = detail.get("materials")
    if not isinstance(materials, list):
        return payload

    public_materials = []
    for index, item in enumerate(materials):
        if not isinstance(item, dict):
            continue
        public_item = {
            "label": str(item.get("label") or f"资料 {index + 1}"),
            "source_index": index,
            "page_url": f"/review-site/materials/{index}",
        }
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            public_item["content"] = content
        raw_url = str(item.get("url") or item.get("href") or "")
        if _is_public_http_url(raw_url):
            public_item["url"] = raw_url
        public_materials.append(public_item)
    detail["materials"] = public_materials
    return payload


def _is_public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _public_source_documents(source_documents_json) -> list:
    documents = []
    for index, item in enumerate(list(source_documents_json or [])):
        if isinstance(item, str):
            label = item.rsplit("/", 1)[-1] or f"来源资料 {index + 1}"
            raw_url = item
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("title") or item.get("name") or f"来源资料 {index + 1}")
            raw_url = str(item.get("url") or item.get("link") or "")
        else:
            continue
        if _is_public_http_url(raw_url):
            documents.append({"label": label, "url": raw_url})
        else:
            documents.append({"label": label, "source_index": index})
    return documents


def day_to_response(day) -> ReviewDayResponse:
    return ReviewDayResponse(
        id=str(day.id),
        day_key=day.day_key,
        day_label=day.day_label,
        phase_key=day.phase_key,
        title=day.title,
        acceptance=day.acceptance,
        scheduled_date=day.scheduled_date.isoformat() if day.scheduled_date else None,
        sort_order=day.sort_order,
        tasks=[],
    )


def progress_to_response(progress) -> ReviewProgressResponse:
    return ReviewProgressResponse(
        id=str(progress.id),
        plan_id=str(progress.plan_id),
        day_id=str(progress.day_id),
        task_id=str(progress.task_id),
        done=bool(progress.done),
        note=progress.note,
        elapsed_minutes=progress.elapsed_minutes,
        mastery_score=progress.mastery_score,
        done_at=progress.done_at.isoformat() if progress.done_at else None,
        created_at=progress.created_at.isoformat() if progress.created_at else None,
        updated_at=progress.updated_at.isoformat() if progress.updated_at else None,
    )


def review_plan_to_response(plan) -> ReviewPlanResponse:
    phases = [
        ReviewPhaseResponse(
            id=str(phase.id),
            phase_key=phase.phase_key,
            title=phase.title,
            range_label=phase.range_label,
            goal=phase.goal,
            sort_order=phase.sort_order,
        )
        for phase in sorted(plan.phases, key=lambda item: item.sort_order)
    ]
    days = []
    for day in sorted(plan.days, key=lambda item: item.sort_order):
        days.append(ReviewDayResponse(
            id=str(day.id),
            day_key=day.day_key,
            day_label=day.day_label,
            phase_key=day.phase_key,
            title=day.title,
            acceptance=day.acceptance,
            scheduled_date=day.scheduled_date.isoformat() if day.scheduled_date else None,
            sort_order=day.sort_order,
            tasks=[task_to_response(task) for task in sorted(day.tasks or [], key=lambda item: item.sort_order)],
        ))
    return ReviewPlanResponse(
        id=str(plan.id),
        plan_key=plan.plan_key,
        title=plan.title,
        subtitle=plan.subtitle,
        description=plan.description,
        status=plan.status,
        source_root="",
        source_documents=_public_source_documents(plan.source_documents_json or []),
        commercial_positioning=list(plan.commercial_positioning_json or []),
        phases=phases,
        days=days,
        progresses=[progress_to_response(item) for item in (plan.progress_records or [])],
        intro_scripts=[
            {
                "id": str(item.id), "script_key": item.script_key, "label": item.label,
                "duration_seconds": item.duration_seconds, "scenario": item.scenario,
                "text": item.text, "sort_order": item.sort_order,
            }
            for item in sorted(plan.intro_scripts or [], key=lambda value: value.sort_order)
        ],
        star_cards=[
            {
                "id": str(item.id), "card_key": item.card_key, "title": item.title,
                "tag": item.tag, "background": item.background, "challenge": item.challenge,
                "solution": item.solution, "result": item.result, "sort_order": item.sort_order,
            }
            for item in sorted(plan.star_cards or [], key=lambda value: value.sort_order)
        ],
        a4_memory=[
            {"id": str(item.id), "content": item.content, "side": item.side, "sort_order": item.sort_order}
            for item in sorted(plan.a4_memory or [], key=lambda value: value.sort_order)
        ],
        metadata=dict(plan.metadata_json or {}),
        created_at=plan.created_at.isoformat() if plan.created_at else None,
        updated_at=plan.updated_at.isoformat() if plan.updated_at else None,
    )
