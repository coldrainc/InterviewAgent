from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import InterviewReportModel, InterviewSessionModel


class InterviewReportRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def upsert_report(
        self,
        *,
        session_id: str | uuid.UUID,
        mode: str,
        total_score: int | None,
        dimension_scores: dict,
        per_question: list,
        evidence: list,
        strength_tags: list,
        weakness_tags: list,
        suggestions: list,
        summary_text: str | None,
        report_version: str = "v1",
        metadata_json: dict | None = None,
    ) -> InterviewReportModel:
        session_uuid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        result = await self.session.execute(
            select(InterviewReportModel).where(
                InterviewReportModel.tenant_id == self.tenant_id,
                InterviewReportModel.user_id == self.user_id,
                InterviewReportModel.session_id == session_uuid,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = InterviewReportModel(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=session_uuid,
                mode=mode,
            )
            self.session.add(model)
        model.mode = mode
        model.total_score = total_score
        model.dimension_scores_json = dimension_scores or {}
        model.per_question_json = per_question or []
        model.evidence_json = evidence or []
        model.strength_tags_json = strength_tags or []
        model.weakness_tags_json = weakness_tags or []
        model.suggestions_json = suggestions or []
        model.summary_text = summary_text
        model.report_version = report_version
        model.metadata_json = metadata_json or {}
        await self.session.flush()
        return model

    async def get_report(self, session_id: str | uuid.UUID) -> dict | None:
        session_uuid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        result = await self.session.execute(
            select(InterviewReportModel)
            .options(selectinload(InterviewReportModel.session))
            .where(
                InterviewReportModel.tenant_id == self.tenant_id,
                InterviewReportModel.user_id == self.user_id,
                InterviewReportModel.session_id == session_uuid,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _report_to_dict(model)

    async def list_reports(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(InterviewReportModel)
            .options(selectinload(InterviewReportModel.session))
            .where(
                InterviewReportModel.tenant_id == self.tenant_id,
                InterviewReportModel.user_id == self.user_id,
            )
            .order_by(InterviewReportModel.created_at.desc())
            .limit(limit)
        )
        return [_report_to_dict(model) for model in result.scalars().all()]


def _report_to_dict(model: InterviewReportModel) -> dict:
    session = model.session
    return {
        "id": str(model.id),
        "session_id": str(model.session_id),
        "mode": model.mode,
        "total_score": model.total_score,
        "verdict": (model.metadata_json or {}).get("verdict"),
        "degraded": bool((model.metadata_json or {}).get("degraded", False)),
        "dimension_scores": model.dimension_scores_json or {},
        "per_question": model.per_question_json or [],
        "evidence": model.evidence_json or [],
        "strength_tags": model.strength_tags_json or [],
        "weakness_tags": model.weakness_tags_json or [],
        "suggestions": model.suggestions_json or [],
        "summary": model.summary_text or "",
        "report_version": model.report_version,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "target_role": getattr(session, "target_role", None) if session else None,
        "candidate_name": getattr(session, "candidate_name", None) if session else None,
        "industry": getattr(session, "industry", None) if session else None,
        "session_status": getattr(session, "status", None) if session else None,
        "plan_task_id": str(getattr(session, "plan_task_id", "")) if session and getattr(session, "plan_task_id", None) else None,
    }
