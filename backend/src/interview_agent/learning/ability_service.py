from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import InterviewReportModel, PracticeAttemptModel, PracticeQuestionModel
from interview_agent.learning.models import LearningAbilitySnapshotModel


class AbilitySnapshotService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def latest(self) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(LearningAbilitySnapshotModel)
            .where(
                LearningAbilitySnapshotModel.tenant_id == self.tenant_id,
                LearningAbilitySnapshotModel.user_id == self.user_id,
            )
            .order_by(LearningAbilitySnapshotModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return snapshot_to_dict(model) if model else None

    async def compute(self, *, goal_id=None) -> dict[str, Any]:
        reports = list((await self.session.execute(
            select(InterviewReportModel).where(
                InterviewReportModel.tenant_id == self.tenant_id,
                InterviewReportModel.user_id == self.user_id,
            )
        )).scalars())
        attempts = list((await self.session.execute(
            select(PracticeAttemptModel, PracticeQuestionModel)
            .join(PracticeQuestionModel, PracticeQuestionModel.id == PracticeAttemptModel.question_id)
            .where(
                PracticeAttemptModel.tenant_id == self.tenant_id,
                PracticeAttemptModel.user_id == self.user_id,
            )
        )).all())
        values: dict[str, list[int]] = defaultdict(list)
        evidence: dict[str, list[str]] = defaultdict(list)
        for report in reports:
            for name, score in (report.dimension_scores_json or {}).items():
                if isinstance(score, (int, float)):
                    values[str(name)].append(max(0, min(100, int(score))))
                    evidence[str(name)].append(str(report.id))
        for attempt, question in attempts:
            dimension = question.subject or question.practice_category or "practice"
            values[dimension].append(int(attempt.score))
            evidence[dimension].append(str(attempt.id))
        dimensions = {
            name: {
                "score": round(sum(scores) / len(scores)),
                "sample_count": len(scores),
                "confidence": min(100, 25 + len(scores) * 15),
            }
            for name, scores in values.items()
        }
        sample_count = len(reports) + len(attempts)
        model = LearningAbilitySnapshotModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            goal_id=goal_id,
            dimensions_json=dimensions,
            evidence_json={name: ids[-10:] for name, ids in evidence.items()},
            confidence=min(100, sample_count * 12),
        )
        self.session.add(model)
        await self.session.flush()
        return snapshot_to_dict(model)


def snapshot_to_dict(model: LearningAbilitySnapshotModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "goal_id": str(model.goal_id) if model.goal_id else None,
        "dimensions": dict(model.dimensions_json or {}),
        "evidence": dict(model.evidence_json or {}),
        "confidence": model.confidence,
        "source": model.source,
        "created_at": model.created_at.isoformat(),
    }
