from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import InterviewSessionModel
from interview_agent.interviewer.models import InterviewerEvidenceModel, InterviewerKitModel

DEFAULT_DIMENSIONS = ["technical_depth", "communication", "problem_solving", "role_fit"]


class InterviewerWorkspaceService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def list_kits(self, *, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        rows = await self.session.execute(
            select(InterviewerKitModel)
            .where(
                InterviewerKitModel.tenant_id == self.tenant_id,
                InterviewerKitModel.user_id == self.user_id,
            )
            .order_by(InterviewerKitModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [kit_to_dict(item, evidence=[]) for item in rows.scalars()]

    async def create_kit(self, payload: dict[str, Any]) -> dict[str, Any]:
        dimensions = [str(item).strip() for item in payload.get("dimensions") or DEFAULT_DIMENSIONS if str(item).strip()]
        questions = payload.get("questions") or self._default_questions(payload.get("target_role", ""), dimensions)
        model = InterviewerKitModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            title=str(payload.get("title") or f"{payload.get('target_role') or '通用'}面试题纲"),
            target_role=str(payload.get("target_role") or "通用岗位"),
            seniority=str(payload.get("seniority") or ""),
            duration_minutes=int(payload.get("duration_minutes") or 45),
            dimensions_json=dimensions,
            questions_json=self._normalize_questions(questions, dimensions),
        )
        self.session.add(model)
        await self.session.flush()
        return kit_to_dict(model, evidence=[])

    async def get(self, kit_id: str) -> dict[str, Any]:
        kit = await self.require_owned_kit(kit_id)
        evidence = list((await self.session.execute(
            select(InterviewerEvidenceModel)
            .where(
                InterviewerEvidenceModel.kit_id == kit.id,
                InterviewerEvidenceModel.tenant_id == self.tenant_id,
                InterviewerEvidenceModel.user_id == self.user_id,
            )
            .order_by(InterviewerEvidenceModel.created_at.asc())
        )).scalars())
        return kit_to_dict(kit, evidence=evidence)

    async def update_questions(self, kit_id: str, questions: list[dict], expected_version: int) -> dict[str, Any]:
        kit = await self.require_owned_kit(kit_id)
        if kit.version != expected_version:
            raise ValueError(f"version conflict: current {kit.version}")
        kit.questions_json = self._normalize_questions(questions, list(kit.dimensions_json or []))
        kit.version += 1
        await self.session.flush()
        return await self.get(kit_id)

    async def add_evidence(self, kit_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        kit = await self.require_owned_kit(kit_id)
        dimension = str(payload.get("dimension") or "").strip()
        if dimension not in kit.dimensions_json:
            raise ValueError("dimension is not part of this kit")
        client_key = str(payload.get("client_key") or uuid.uuid4())[:128]
        existing = (await self.session.execute(select(InterviewerEvidenceModel).where(
            InterviewerEvidenceModel.tenant_id == self.tenant_id,
            InterviewerEvidenceModel.user_id == self.user_id,
            InterviewerEvidenceModel.kit_id == kit.id,
            InterviewerEvidenceModel.client_key == client_key,
        ))).scalar_one_or_none()
        if existing:
            return evidence_to_dict(existing)
        session_id = await self._validate_evidence_session(kit, payload.get("session_id"))
        model = InterviewerEvidenceModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            kit_id=kit.id,
            session_id=session_id,
            client_key=client_key,
            dimension=dimension,
            signal=str(payload.get("signal") or "neutral"),
            note=str(payload.get("note") or "")[:4000],
            quote=str(payload.get("quote") or "")[:4000] or None,
        )
        self.session.add(model)
        await self.session.flush()
        return evidence_to_dict(model)

    async def require_owned_kit(self, kit_id: str) -> InterviewerKitModel:
        try:
            kit = await self._kit(kit_id)
        except (TypeError, ValueError):
            kit = None
        if kit is None:
            raise LookupError("kit not found")
        return kit

    async def _validate_evidence_session(
        self,
        kit: InterviewerKitModel,
        session_id: str | None,
    ) -> uuid.UUID | None:
        if not session_id:
            return None
        try:
            parsed_id = uuid.UUID(session_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid session_id") from exc
        result = await self.session.execute(
            select(InterviewSessionModel).where(
                InterviewSessionModel.id == parsed_id,
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
                InterviewSessionModel.interviewer_kit_id == kit.id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("session is not linked to this kit")
        return parsed_id

    async def _kit(self, kit_id: str):
        result = await self.session.execute(select(InterviewerKitModel).where(
            InterviewerKitModel.id == uuid.UUID(kit_id),
            InterviewerKitModel.tenant_id == self.tenant_id,
            InterviewerKitModel.user_id == self.user_id,
        ))
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_questions(questions, dimensions):
        return [{
            "id": str(item.get("id") or uuid.uuid4()),
            "text": str(item.get("text") or "").strip()[:2000],
            "dimension": str(item.get("dimension") or dimensions[0] if dimensions else "general"),
            "followups": [str(value)[:1000] for value in item.get("followups") or []],
            "locked": bool(item.get("locked")),
        } for item in questions if str(item.get("text") or "").strip()]

    @staticmethod
    def _default_questions(role: str, dimensions: list[str]) -> list[dict[str, Any]]:
        labels = dimensions or DEFAULT_DIMENSIONS
        return [
            {"text": f"请介绍一个最能体现你胜任{role or '该岗位'}的项目，并说明你的具体贡献。", "dimension": labels[0], "followups": ["最难的取舍是什么？", "结果如何量化？"]},
            {"text": "遇到信息不完整的问题时，你会如何澄清、拆解并推进？", "dimension": labels[min(2, len(labels) - 1)], "followups": ["请给出真实案例。"]},
            {"text": "请复盘一次失败或结果不及预期的经历。", "dimension": labels[min(1, len(labels) - 1)], "followups": ["之后改变了什么？"]},
        ]


def kit_to_dict(model, *, evidence):
    return {"id": str(model.id), "title": model.title, "target_role": model.target_role, "seniority": model.seniority, "duration_minutes": model.duration_minutes, "dimensions": list(model.dimensions_json or []), "questions": list(model.questions_json or []), "status": model.status, "version": model.version, "evidence": [evidence_to_dict(item) for item in evidence]}


def evidence_to_dict(model):
    return {"id": str(model.id), "dimension": model.dimension, "signal": model.signal, "note": model.note, "quote": model.quote, "session_id": str(model.session_id) if model.session_id else None, "created_at": model.created_at.isoformat()}
