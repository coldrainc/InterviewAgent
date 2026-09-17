from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import PracticeQuestionModel
from interview_agent.repositories.practice_question_repository import question_to_dict
from interview_agent.training.models import TrainingDrillModel


class TrainingDrillService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def create(self, *, focus: str, count: int = 10, difficulty: str | None = None) -> dict[str, Any]:
        filters = [
            PracticeQuestionModel.tenant_id == self.tenant_id,
            PracticeQuestionModel.user_id == self.user_id,
        ]
        normalized = focus.strip()
        if normalized:
            filters.append(
                (PracticeQuestionModel.subject == normalized)
                | (PracticeQuestionModel.practice_category == normalized)
            )
        if difficulty:
            filters.append(PracticeQuestionModel.difficulty == difficulty)
        rows = await self.session.execute(
            select(PracticeQuestionModel).where(*filters).order_by(func.random()).limit(max(1, min(50, count)))
        )
        questions = list(rows.scalars())
        if not questions:
            raise ValueError("no questions match this focus")
        model = TrainingDrillModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            focus=normalized or "综合",
            question_ids_json=[str(item.id) for item in questions],
        )
        self.session.add(model)
        await self.session.flush()
        return drill_to_dict(model, questions)

    async def get(self, drill_id: str) -> dict[str, Any]:
        model = await self._get(drill_id)
        if model is None:
            raise LookupError("drill not found")
        ids = [uuid.UUID(item) for item in model.question_ids_json or []]
        questions = []
        if ids:
            questions = list((await self.session.execute(
                select(PracticeQuestionModel).where(
                    PracticeQuestionModel.id.in_(ids),
                    PracticeQuestionModel.tenant_id == self.tenant_id,
                    PracticeQuestionModel.user_id == self.user_id,
                )
            )).scalars())
            order = {value: index for index, value in enumerate(ids)}
            questions.sort(key=lambda item: order[item.id])
        return drill_to_dict(model, questions)

    async def complete(self, drill_id: str) -> dict[str, Any]:
        model = await self._get(drill_id)
        if model is None:
            raise LookupError("drill not found")
        model.status = "completed"
        model.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return await self.get(drill_id)

    async def _get(self, drill_id: str):
        result = await self.session.execute(select(TrainingDrillModel).where(
            TrainingDrillModel.id == uuid.UUID(drill_id),
            TrainingDrillModel.tenant_id == self.tenant_id,
            TrainingDrillModel.user_id == self.user_id,
        ))
        return result.scalar_one_or_none()


def drill_to_dict(model, questions):
    return {
        "id": str(model.id),
        "focus": model.focus,
        "source": model.source,
        "status": model.status,
        "question_count": len(model.question_ids_json or []),
        "questions": [question_to_dict(item) for item in questions],
        "created_at": model.created_at.isoformat(),
        "completed_at": model.completed_at.isoformat() if model.completed_at else None,
    }
