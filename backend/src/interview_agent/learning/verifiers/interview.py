from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from interview_agent.infrastructure.db.models import InterviewSessionModel
from interview_agent.learning.verifiers.base import VerificationResult


class InterviewTaskVerifier:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def verify(self, task: Any, run: Any, submitted: dict[str, Any]) -> VerificationResult:
        result = await self.session.execute(
            select(InterviewSessionModel)
            .options(selectinload(InterviewSessionModel.report))
            .where(
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
                InterviewSessionModel.plan_task_id == task.id,
            )
            .order_by(InterviewSessionModel.updated_at.desc())
            .limit(1)
        )
        interview = result.scalar_one_or_none()
        if interview is not None and interview.status == "completed" and interview.report is not None:
            return VerificationResult(
                status="verified",
                mode="automatic",
                reason="关联模拟面试已完成并生成报告",
                evidence={"session_id": str(interview.id), "report_id": str(interview.report.id)},
                verifier="interview_report",
            )
        return VerificationResult(
            status="rejected",
            mode="automatic",
            reason="请先完成关联模拟面试并生成报告",
            verifier="interview_report",
        )
