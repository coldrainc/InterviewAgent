from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db import models as db_models
from interview_agent.interviewer import models as interviewer_models
from interview_agent.learning import models as learning_models
from interview_agent.training import models as training_models


EXPORT_GROUPS = {
    "account": (db_models.UserAccountModel,),
    "billing": (
        db_models.CreditLedgerModel,
        db_models.RechargeOrderModel,
        db_models.UsageRecordModel,
    ),
    "interviews": (
        db_models.ResumeModel,
        db_models.InterviewSessionModel,
        db_models.MemoryItemModel,
        db_models.InterviewReportModel,
    ),
    "planning": (
        db_models.ReviewPlanModel,
        db_models.ReviewDayModel,
        db_models.ReviewTaskModel,
        db_models.ReviewProgressModel,
        db_models.ReviewCheckinModel,
        db_models.IntroScriptModel,
        db_models.StarCardModel,
        db_models.A4MemoryItemModel,
    ),
    "practice": (
        db_models.PracticeQuestionModel,
        db_models.PracticeWrongBookModel,
        db_models.PracticeAttemptModel,
        db_models.CivilServiceQuestionModel,
    ),
    "learning": (
        learning_models.LearningGoalModel,
        learning_models.LearningPlanVersionModel,
        learning_models.LearningAbilitySnapshotModel,
        learning_models.LearningTaskRunModel,
        learning_models.LearningEvidenceModel,
        learning_models.LearningVerificationModel,
        learning_models.LearningEffectReceiptModel,
        learning_models.LearningPlanRevisionModel,
    ),
    "interviewer_training": (
        interviewer_models.InterviewerKitModel,
        interviewer_models.InterviewerEvidenceModel,
        training_models.TrainingDrillModel,
        training_models.SpacedReviewItemModel,
    ),
}

SECRET_FIELDS = {"password_hash", "token_hash"}


class UserDataExportService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def export(self) -> dict[str, Any]:
        groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for group, models in EXPORT_GROUPS.items():
            groups[group] = {}
            for model in models:
                rows = await self.session.execute(
                    select(model).where(
                        model.tenant_id == self.tenant_id,
                        model.user_id == self.user_id,
                    )
                )
                groups[group][model.__tablename__] = [self._serialize(item) for item in rows.scalars()]
        groups["interviews"]["interview_turns"] = await self._owned_interview_turns()
        return {
            "schema_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "excluded": ["password hashes", "auth tokens", "payment credentials", "raw object binaries"],
            "data": groups,
        }

    async def _owned_interview_turns(self) -> list[dict[str, Any]]:
        rows = await self.session.execute(
            select(db_models.InterviewTurnModel)
            .join(
                db_models.InterviewSessionModel,
                db_models.InterviewSessionModel.id == db_models.InterviewTurnModel.session_id,
            )
            .where(
                db_models.InterviewSessionModel.tenant_id == self.tenant_id,
                db_models.InterviewSessionModel.user_id == self.user_id,
            )
        )
        return [self._serialize(item) for item in rows.scalars()]

    @staticmethod
    def _serialize(model) -> dict[str, Any]:
        return {
            column.name: _json_value(getattr(model, column.name))
            for column in model.__table__.columns
            if column.name not in SECRET_FIELDS
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    return value
