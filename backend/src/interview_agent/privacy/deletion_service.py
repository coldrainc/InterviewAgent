from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db import models as db_models
from interview_agent.infrastructure.object_storage import ObjectStorage
from interview_agent.interviewer import models as interviewer_models
from interview_agent.learning import models as learning_models
from interview_agent.privacy.models import DataDeletionRequestModel
from interview_agent.services.security_service import SecurityService
from interview_agent.training import models as training_models


COOLING_OFF_DAYS = 7

PRODUCT_MODELS_DELETE_ORDER = (
    interviewer_models.InterviewerEvidenceModel,
    training_models.SpacedReviewItemModel,
    training_models.TrainingDrillModel,
    learning_models.LearningEffectReceiptModel,
    learning_models.LearningEvidenceModel,
    learning_models.LearningVerificationModel,
    learning_models.LearningTaskRunModel,
    learning_models.LearningPlanRevisionModel,
    learning_models.LearningPlanVersionModel,
    learning_models.LearningAbilitySnapshotModel,
    learning_models.LearningGoalModel,
    db_models.UserAchievementModel,
    db_models.ReviewCheckinModel,
    db_models.ReviewProgressModel,
    db_models.A4MemoryItemModel,
    db_models.StarCardModel,
    db_models.IntroScriptModel,
    db_models.ReviewTaskModel,
    db_models.ReviewDayModel,
    db_models.ReviewPhaseModel,
    db_models.ReviewPlanModel,
    db_models.PracticeAttemptModel,
    db_models.PracticeWrongBookModel,
    db_models.PracticeQuestionModel,
    db_models.CivilServiceQuestionModel,
    db_models.InterviewReportModel,
    db_models.InterviewSessionModel,
    db_models.ResumeModel,
    interviewer_models.InterviewerKitModel,
    db_models.AgentTraceModel,
    db_models.EvalRunModel,
    db_models.EvalDatasetModel,
    db_models.JobModel,
)


class DataDeletionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
        object_storage: ObjectStorage | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.object_storage = object_storage

    async def current(self) -> dict | None:
        request = await self._active()
        return deletion_request_to_dict(request) if request else None

    async def schedule(self, *, reason: str = "") -> dict:
        existing = await self._active()
        if existing:
            return deletion_request_to_dict(existing)
        now = datetime.now(timezone.utc)
        model = DataDeletionRequestModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            status="scheduled",
            reason=reason[:2000] or None,
            scope_json={
                "delete": "product_data",
                "retain": ["billing_ledger", "security_audit", "deletion_audit"],
            },
            requested_at=now,
            execute_after=now + timedelta(days=COOLING_OFF_DAYS),
        )
        self.session.add(model)
        await self.session.flush()
        return deletion_request_to_dict(model)

    async def cancel(self) -> dict:
        model = await self._active()
        if model is None:
            raise LookupError("no scheduled deletion request")
        model.status = "cancelled"
        model.cancelled_at = datetime.now(timezone.utc)
        await self.session.flush()
        return deletion_request_to_dict(model)

    async def execute_if_due(self, *, now: datetime | None = None) -> dict:
        model = await self._active()
        if model is None:
            raise LookupError("no scheduled deletion request")
        current_time = now or datetime.now(timezone.utc)
        execute_after = _aware(model.execute_after)
        if current_time < execute_after:
            raise ValueError("deletion request is still in cooling-off period")
        await self._delete_resume_objects()
        deleted: dict[str, int] = {}
        deleted.update(await self._delete_owned_children())
        session_ids = select(db_models.InterviewSessionModel.id).where(
            db_models.InterviewSessionModel.tenant_id == self.tenant_id,
            db_models.InterviewSessionModel.user_id == self.user_id,
        )
        memories = await self.session.execute(
            delete(db_models.MemoryItemModel).where(
                db_models.MemoryItemModel.tenant_id == self.tenant_id,
                db_models.MemoryItemModel.user_id == self.user_id,
            )
        )
        deleted[db_models.MemoryItemModel.__tablename__] = int(memories.rowcount or 0)
        turns = await self.session.execute(
            delete(db_models.InterviewTurnModel).where(
                db_models.InterviewTurnModel.session_id.in_(session_ids)
            )
        )
        deleted[db_models.InterviewTurnModel.__tablename__] = int(turns.rowcount or 0)
        for owned_model in PRODUCT_MODELS_DELETE_ORDER:
            result = await self.session.execute(
                delete(owned_model).where(
                    owned_model.tenant_id == self.tenant_id,
                    owned_model.user_id == self.user_id,
                )
            )
            deleted[owned_model.__tablename__] = int(result.rowcount or 0)
        account = (
            await self.session.execute(
                select(db_models.UserAccountModel).where(
                    db_models.UserAccountModel.tenant_id == self.tenant_id,
                    db_models.UserAccountModel.user_id == self.user_id,
                )
            )
        ).scalar_one_or_none()
        if account:
            account.email = None
            account.password_hash = None
            account.display_name = "Deleted user"
            account.status = "deleted"
            account.metadata_json = {"deleted_at": current_time.isoformat()}
        await SecurityService(self.session, tenant_id=self.tenant_id).revoke_user_refresh_tokens(
            self.user_id
        )
        model.status = "executed"
        model.executed_at = current_time
        model.scope_json = {**dict(model.scope_json or {}), "deleted_counts": deleted}
        await self.session.flush()
        return deletion_request_to_dict(model)

    async def _delete_owned_children(self) -> dict[str, int]:
        job_ids = select(db_models.JobModel.id).where(
            db_models.JobModel.tenant_id == self.tenant_id,
            db_models.JobModel.user_id == self.user_id,
        )
        trace_ids = select(db_models.AgentTraceModel.id).where(
            db_models.AgentTraceModel.tenant_id == self.tenant_id,
            db_models.AgentTraceModel.user_id == self.user_id,
        )
        dataset_ids = select(db_models.EvalDatasetModel.id).where(
            db_models.EvalDatasetModel.tenant_id == self.tenant_id,
            db_models.EvalDatasetModel.user_id == self.user_id,
        )
        run_ids = select(db_models.EvalRunModel.id).where(
            db_models.EvalRunModel.tenant_id == self.tenant_id,
            db_models.EvalRunModel.user_id == self.user_id,
        )
        statements = (
            (db_models.AgentSpanModel, db_models.AgentSpanModel.trace_id.in_(trace_ids)),
            (db_models.EvalResultModel, db_models.EvalResultModel.run_id.in_(run_ids)),
            (db_models.EvalCaseModel, db_models.EvalCaseModel.dataset_id.in_(dataset_ids)),
            (db_models.JobEventModel, db_models.JobEventModel.job_id.in_(job_ids)),
            (db_models.JobStepModel, db_models.JobStepModel.job_id.in_(job_ids)),
        )
        deleted = {}
        for model, predicate in statements:
            result = await self.session.execute(delete(model).where(predicate))
            deleted[model.__tablename__] = int(result.rowcount or 0)
        return deleted

    async def _delete_resume_objects(self) -> None:
        if self.object_storage is None:
            return
        rows = await self.session.execute(
            select(db_models.ResumeModel.object_bucket, db_models.ResumeModel.object_key).where(
                db_models.ResumeModel.tenant_id == self.tenant_id,
                db_models.ResumeModel.user_id == self.user_id,
                db_models.ResumeModel.object_key.is_not(None),
            )
        )
        for bucket, key in rows.all():
            if bucket and key:
                referenced = await self.session.scalar(
                    select(db_models.ResumeModel.id).where(
                        db_models.ResumeModel.object_bucket == bucket,
                        db_models.ResumeModel.object_key == key,
                        ~(
                            (db_models.ResumeModel.tenant_id == self.tenant_id)
                            & (db_models.ResumeModel.user_id == self.user_id)
                        ),
                    ).limit(1)
                )
                if referenced is None:
                    await asyncio.to_thread(self.object_storage.delete_object, bucket, key)

    async def _active(self) -> DataDeletionRequestModel | None:
        result = await self.session.execute(
            select(DataDeletionRequestModel)
            .where(
                DataDeletionRequestModel.tenant_id == self.tenant_id,
                DataDeletionRequestModel.user_id == self.user_id,
                DataDeletionRequestModel.status == "scheduled",
            )
            .order_by(DataDeletionRequestModel.requested_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def deletion_request_to_dict(model: DataDeletionRequestModel) -> dict:
    return {
        "id": str(model.id),
        "status": model.status,
        "reason": model.reason,
        "scope": dict(model.scope_json or {}),
        "requested_at": model.requested_at.isoformat(),
        "execute_after": model.execute_after.isoformat(),
        "cancelled_at": model.cancelled_at.isoformat() if model.cancelled_at else None,
        "executed_at": model.executed_at.isoformat() if model.executed_at else None,
    }


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def execute_due_deletions(
    session: AsyncSession,
    *,
    object_storage: ObjectStorage,
    now: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    current_time = now or datetime.now(timezone.utc)
    rows = await session.execute(
        select(DataDeletionRequestModel)
        .where(
            DataDeletionRequestModel.status == "scheduled",
            DataDeletionRequestModel.execute_after <= current_time,
        )
        .order_by(DataDeletionRequestModel.execute_after.asc())
        .limit(limit)
    )
    results = []
    for request in rows.scalars():
        result = await DataDeletionService(
                session,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                object_storage=object_storage,
            ).execute_if_due(now=current_time)
        results.append(
            {"tenant_id": request.tenant_id, "user_id": request.user_id, "request": result}
        )
    return results
