from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interviewer.service import InterviewerWorkspaceService
from interview_agent.learning.routes.dependencies import require_authenticated

router = APIRouter(prefix="/interviewer-workspace", tags=["interviewer"])


class KitRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    target_role: str = Field(min_length=1, max_length=255)
    seniority: str = Field(default="", max_length=128)
    duration_minutes: int = Field(default=45, ge=15, le=240)
    dimensions: list[str] = Field(default_factory=list, max_length=12)
    questions: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class QuestionUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    questions: list[dict[str, Any]] = Field(max_length=50)


class EvidenceRequest(BaseModel):
    client_key: str | None = Field(default=None, max_length=128)
    session_id: str | None = None
    dimension: str = Field(min_length=1, max_length=64)
    signal: str = Field(default="neutral", pattern="^(positive|neutral|negative|unknown)$")
    note: str = Field(min_length=1, max_length=4000)
    quote: str | None = Field(default=None, max_length=4000)


@router.post("/kits")
async def create_kit(request: KitRequest, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        return await InterviewerWorkspaceService(db, tenant_id=context.tenant_id, user_id=context.user_id).create_kit(request.model_dump())


@router.get("/kits")
async def list_kits(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(request_context),
):
    require_authenticated(context)
    async with session_scope() as db:
        return await InterviewerWorkspaceService(
            db, tenant_id=context.tenant_id, user_id=context.user_id
        ).list_kits(limit=limit, offset=offset)


@router.get("/kits/{kit_id}")
async def get_kit(kit_id: str, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await InterviewerWorkspaceService(db, tenant_id=context.tenant_id, user_id=context.user_id).get(kit_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="kit not found") from exc


@router.put("/kits/{kit_id}/questions")
async def update_questions(kit_id: str, request: QuestionUpdateRequest, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await InterviewerWorkspaceService(db, tenant_id=context.tenant_id, user_id=context.user_id).update_questions(kit_id, request.questions, request.expected_version)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="kit not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/kits/{kit_id}/evidence")
async def add_evidence(kit_id: str, request: EvidenceRequest, context: RequestContext = Depends(request_context)):
    require_authenticated(context)
    async with session_scope() as db:
        try:
            return await InterviewerWorkspaceService(db, tenant_id=context.tenant_id, user_id=context.user_id).add_evidence(kit_id, request.model_dump())
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="kit not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
