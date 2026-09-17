from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.routes.review_plans import _require_authenticated
from interview_agent.interfaces.schemas import (
    A4MemoryResponse,
    IntroScriptResponse,
    MaterialItemRequest,
    StarCardResponse,
)
from interview_agent.repositories.review_site_repository import ReviewSiteRepository


MATERIAL_KINDS = ("intro_scripts", "star_cards", "a4_memory")


def create_review_materials_router() -> APIRouter:
    router = APIRouter()

    @router.post("/review-site/plans/{plan_id}/materials/{kind}", status_code=201)
    async def create_material_item(
        plan_id: str,
        kind: str,
        request: MaterialItemRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        _validate_kind(kind)
        async with session_scope() as db:
            repo = _repository(db, context)
            try:
                item = await repo.upsert_material_item(plan_id, kind, request.model_dump(exclude_none=True))
            except ValueError:
                raise HTTPException(status_code=404, detail="plan not found") from None
            if item is None:
                raise HTTPException(status_code=404, detail="plan not found")
            await db.refresh(item)
            return material_item_to_dict(kind, item)

    @router.patch("/review-site/materials/{kind}/{item_id}")
    async def update_material_item(
        kind: str,
        item_id: str,
        request: MaterialItemRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        _validate_kind(kind)
        async with session_scope() as db:
            repo = _repository(db, context)
            try:
                existing = await repo.get_material_item(kind, item_id)
            except ValueError:
                existing = None
            if existing is None:
                raise HTTPException(status_code=404, detail="material not found")
            item = await repo.upsert_material_item(
                str(existing.plan_id), kind, request.model_dump(exclude_none=True), item_id=item_id
            )
            await db.refresh(item)
            return material_item_to_dict(kind, item)

    @router.delete("/review-site/materials/{kind}/{item_id}")
    async def delete_material_item(
        kind: str,
        item_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        _validate_kind(kind)
        async with session_scope() as db:
            try:
                deleted = await _repository(db, context).delete_material_item(kind, item_id)
            except ValueError:
                deleted = False
        if not deleted:
            raise HTTPException(status_code=404, detail="material not found")
        return {"deleted": True}

    @router.get("/review-site/plans/{plan_id}/intro-scripts", response_model=list[IntroScriptResponse])
    async def list_intro_scripts(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> list[IntroScriptResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            items = await _repository(db, context).list_intro_scripts(plan_id)
        return [
            IntroScriptResponse(
                id=str(item.id),
                script_key=item.script_key,
                label=item.label,
                duration_seconds=item.duration_seconds,
                scenario=item.scenario,
                text=item.text,
                sort_order=item.sort_order,
            )
            for item in items
        ]

    @router.get("/review-site/plans/{plan_id}/star-cards", response_model=list[StarCardResponse])
    async def list_star_cards(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> list[StarCardResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            items = await _repository(db, context).list_star_cards(plan_id)
        return [
            StarCardResponse(
                id=str(item.id),
                card_key=item.card_key,
                title=item.title,
                tag=item.tag,
                background=item.background,
                challenge=item.challenge,
                solution=item.solution,
                result=item.result,
                sort_order=item.sort_order,
            )
            for item in items
        ]

    @router.get("/review-site/plans/{plan_id}/a4-memory", response_model=list[A4MemoryResponse])
    async def list_a4_memory(
        plan_id: str,
        context: RequestContext = Depends(request_context),
    ) -> list[A4MemoryResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            items = await _repository(db, context).list_a4_memory(plan_id)
        return [
            A4MemoryResponse(
                id=str(item.id),
                content=item.content,
                side=item.side,
                sort_order=item.sort_order,
            )
            for item in items
        ]

    return router


def _repository(db, context: RequestContext) -> ReviewSiteRepository:
    return ReviewSiteRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)


def _validate_kind(kind: str) -> None:
    if kind not in MATERIAL_KINDS:
        raise HTTPException(status_code=400, detail="kind must be intro_scripts, star_cards or a4_memory")


def material_item_to_dict(kind: str, item) -> dict:
    if kind == "intro_scripts":
        return IntroScriptResponse(
            id=str(item.id), script_key=item.script_key, label=item.label,
            duration_seconds=item.duration_seconds, scenario=item.scenario,
            text=item.text, sort_order=item.sort_order,
        ).model_dump()
    if kind == "star_cards":
        return StarCardResponse(
            id=str(item.id), card_key=item.card_key, title=item.title,
            tag=item.tag, background=item.background, challenge=item.challenge,
            solution=item.solution, result=item.result, sort_order=item.sort_order,
        ).model_dump()
    return A4MemoryResponse(
        id=str(item.id), content=item.content, side=item.side, sort_order=item.sort_order,
    ).model_dump()
