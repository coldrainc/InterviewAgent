from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import PracticeQuestionModel, PracticeWrongBookModel
from interview_agent.repositories.practice_question_repository import question_to_dict
from interview_agent.training.models import SpacedReviewItemModel


class SpacedReviewService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def sync_wrong_book(self) -> dict[str, int]:
        rows = await self.session.execute(select(PracticeWrongBookModel).where(
            PracticeWrongBookModel.tenant_id == self.tenant_id,
            PracticeWrongBookModel.user_id == self.user_id,
            PracticeWrongBookModel.mark_type == "wrong",
        ))
        created = 0
        for entry in rows.scalars():
            existing = await self._by_question(entry.question_id)
            if existing is None:
                self.session.add(SpacedReviewItemModel(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    question_id=entry.question_id,
                    metadata_json={"wrong_book_id": str(entry.id)},
                ))
                created += 1
        await self.session.flush()
        return {"created": created}

    async def due(self, *, limit: int = 20, now: datetime | None = None) -> dict[str, Any]:
        target = now or datetime.now(timezone.utc)
        rows = await self.session.execute(
            select(SpacedReviewItemModel, PracticeQuestionModel)
            .join(PracticeQuestionModel, PracticeQuestionModel.id == SpacedReviewItemModel.question_id)
            .where(
                SpacedReviewItemModel.tenant_id == self.tenant_id,
                SpacedReviewItemModel.user_id == self.user_id,
                SpacedReviewItemModel.due_at <= target,
                SpacedReviewItemModel.state != "mastered",
            )
            .order_by(SpacedReviewItemModel.due_at.asc())
            .limit(max(1, min(100, limit)))
        )
        items = [review_to_dict(review, question) for review, question in rows.all()]
        return {"items": items, "total": len(items), "as_of": target.isoformat()}

    async def grade(self, item_id: str, quality: int) -> dict[str, Any]:
        quality = max(0, min(5, int(quality)))
        result = await self.session.execute(select(SpacedReviewItemModel).where(
            SpacedReviewItemModel.id == uuid.UUID(item_id),
            SpacedReviewItemModel.tenant_id == self.tenant_id,
            SpacedReviewItemModel.user_id == self.user_id,
        ))
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("review item not found")
        now = datetime.now(timezone.utc)
        if quality < 3:
            model.repetitions = 0
            model.lapses += 1
            model.interval_days = 1
            model.ease_score = max(130, model.ease_score - 20)
            model.state = "relearning"
        else:
            model.repetitions += 1
            model.ease_score = max(130, model.ease_score + (quality - 3) * 10)
            if model.repetitions == 1:
                model.interval_days = 1
            elif model.repetitions == 2:
                model.interval_days = 3
            else:
                model.interval_days = max(4, round(model.interval_days * model.ease_score / 100))
            model.state = "mastered" if model.repetitions >= 5 and quality >= 4 else "review"
        model.last_reviewed_at = now
        model.due_at = now + timedelta(days=model.interval_days)
        await self.session.flush()
        question = (await self.session.execute(select(PracticeQuestionModel).where(
            PracticeQuestionModel.id == model.question_id
        ))).scalar_one()
        return review_to_dict(model, question)

    async def _by_question(self, question_id):
        result = await self.session.execute(select(SpacedReviewItemModel).where(
            SpacedReviewItemModel.tenant_id == self.tenant_id,
            SpacedReviewItemModel.user_id == self.user_id,
            SpacedReviewItemModel.question_id == question_id,
        ))
        return result.scalar_one_or_none()


def review_to_dict(model, question):
    return {
        "id": str(model.id),
        "question_id": str(model.question_id),
        "state": model.state,
        "interval_days": model.interval_days,
        "repetitions": model.repetitions,
        "lapses": model.lapses,
        "due_at": model.due_at.isoformat(),
        "question": question_to_dict(question),
    }
