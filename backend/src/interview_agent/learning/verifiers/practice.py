from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import PracticeAttemptModel, PracticeQuestionModel
from interview_agent.learning.verifiers.base import VerificationResult


class PracticeTaskVerifier:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def verify(self, task: Any, run: Any, submitted: dict[str, Any]) -> VerificationResult:
        payload = dict(task.link_payload_json or {})
        filters = [
            PracticeAttemptModel.tenant_id == self.tenant_id,
            PracticeAttemptModel.user_id == self.user_id,
        ]
        question_id = payload.get("question_id")
        if question_id:
            try:
                filters.append(PracticeAttemptModel.question_id == uuid.UUID(str(question_id)))
            except ValueError:
                return VerificationResult(
                    status="rejected", mode="automatic", reason="任务关联的题目编号无效", verifier="practice_attempt"
                )
        if payload.get("category"):
            filters.append(PracticeQuestionModel.practice_category == str(payload["category"]))
        if payload.get("subject"):
            filters.append(PracticeQuestionModel.subject == str(payload["subject"]))
        if run.started_at is not None:
            filters.append(PracticeAttemptModel.created_at >= run.started_at)
        result = await self.session.execute(
            select(PracticeAttemptModel)
            .join(PracticeQuestionModel, PracticeQuestionModel.id == PracticeAttemptModel.question_id)
            .where(*filters)
            .order_by(PracticeAttemptModel.created_at.desc())
            .limit(1)
        )
        attempt = result.scalar_one_or_none()
        if attempt is not None:
            return VerificationResult(
                status="verified",
                mode="automatic",
                reason="任务开始后已记录匹配的刷题作答",
                evidence={"attempt_id": str(attempt.id), "question_id": str(attempt.question_id)},
                verifier="practice_attempt",
            )
        return VerificationResult(
            status="rejected",
            mode="automatic",
            reason="请先启动任务并完成至少一道匹配题目",
            verifier="practice_attempt",
        )
