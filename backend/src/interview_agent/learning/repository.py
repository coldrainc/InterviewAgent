from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import ReviewProgressModel, ReviewTaskModel
from interview_agent.learning.errors import VersionConflictError
from interview_agent.learning.models import (
    LearningEffectReceiptModel,
    LearningEvidenceModel,
    LearningTaskRunModel,
    LearningVerificationModel,
)
from interview_agent.learning.projector import task_status


class LearningRepository:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def get_task(self, task_id: str | uuid.UUID) -> ReviewTaskModel | None:
        parsed = _uuid(task_id)
        result = await self.session.execute(
            select(ReviewTaskModel).where(
                ReviewTaskModel.id == parsed,
                ReviewTaskModel.tenant_id == self.tenant_id,
                ReviewTaskModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_run(self, task_id: str | uuid.UUID) -> LearningTaskRunModel | None:
        parsed = _uuid(task_id)
        result = await self.session.execute(
            select(LearningTaskRunModel).where(
                LearningTaskRunModel.task_id == parsed,
                LearningTaskRunModel.tenant_id == self.tenant_id,
                LearningTaskRunModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_run(
        self, task: ReviewTaskModel, progress: ReviewProgressModel
    ) -> LearningTaskRunModel:
        run = await self.get_run(task.id)
        if run is None:
            metadata = dict(progress.metadata_json or {})
            run = LearningTaskRunModel(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                plan_id=task.plan_id,
                task_id=task.id,
                progress_id=progress.id,
                status=task_status(
                    done=bool(progress.done),
                    elapsed_minutes=int(progress.elapsed_minutes or 0),
                    metadata=metadata,
                ),
            )
            self.session.add(run)
            await self.session.flush()
            await self._backfill_legacy_receipts(run, metadata)
        return run

    async def get_receipt_by_key(self, key: str) -> LearningEffectReceiptModel | None:
        result = await self.session.execute(
            select(LearningEffectReceiptModel).where(
                LearningEffectReceiptModel.tenant_id == self.tenant_id,
                LearningEffectReceiptModel.user_id == self.user_id,
                LearningEffectReceiptModel.idempotency_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def latest_receipt(self, run_id: uuid.UUID) -> LearningEffectReceiptModel | None:
        result = await self.session.execute(
            select(LearningEffectReceiptModel)
            .where(
                LearningEffectReceiptModel.run_id == run_id,
                LearningEffectReceiptModel.tenant_id == self.tenant_id,
                LearningEffectReceiptModel.user_id == self.user_id,
            )
            .order_by(LearningEffectReceiptModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def advance_run(
        self,
        run: LearningTaskRunModel,
        *,
        expected_version: int,
        status: str,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> LearningTaskRunModel:
        statement = (
            update(LearningTaskRunModel)
            .where(
                LearningTaskRunModel.id == run.id,
                LearningTaskRunModel.tenant_id == self.tenant_id,
                LearningTaskRunModel.user_id == self.user_id,
                LearningTaskRunModel.version == expected_version,
            )
            .values(
                status=status,
                version=expected_version + 1,
                started_at=started_at,
                completed_at=completed_at,
                updated_at=datetime.now().astimezone(),
            )
        )
        result = await self.session.execute(statement)
        if result.rowcount != 1:
            await self.session.refresh(run)
            raise VersionConflictError(expected=expected_version, current=run.version)
        await self.session.refresh(run)
        return run

    async def add_evidence(
        self, run: LearningTaskRunModel, *, kind: str, source_type: str, source_id: str | None, payload: dict
    ) -> LearningEvidenceModel:
        model = LearningEvidenceModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            run_id=run.id,
            kind=kind,
            source_type=source_type,
            source_id=source_id,
            payload_json=payload,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def add_verification(self, run: LearningTaskRunModel, result) -> LearningVerificationModel:
        model = LearningVerificationModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            run_id=run.id,
            status=result.status,
            mode=result.mode,
            reason=result.reason,
            evidence_json=result.evidence,
            verifier=result.verifier,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def add_receipt(
        self,
        run: LearningTaskRunModel,
        *,
        idempotency_key: str,
        action: str,
        previous_status: str,
        previous_version: int,
        accepted: bool,
        receipt: dict[str, Any],
        verification_id: uuid.UUID | None,
    ) -> LearningEffectReceiptModel:
        model = LearningEffectReceiptModel(
            id=uuid.UUID(receipt["receipt_id"]),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            run_id=run.id,
            task_id=run.task_id,
            verification_id=verification_id,
            idempotency_key=idempotency_key,
            action=action,
            previous_status=previous_status,
            current_status=run.status,
            previous_version=previous_version,
            current_version=run.version,
            accepted=accepted,
            receipt_json=receipt,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def _backfill_legacy_receipts(self, run: LearningTaskRunModel, metadata: dict[str, Any]) -> None:
        receipts = list((metadata.get("learning_harness") or {}).get("receipts") or [])
        version = 0
        for item in receipts:
            receipt = dict(item or {})
            receipt_id = _optional_uuid(receipt.get("receipt_id")) or uuid.uuid4()
            version += 1
            current_status = str(receipt.get("current_status") or run.status)
            model = LearningEffectReceiptModel(
                id=receipt_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                run_id=run.id,
                task_id=run.task_id,
                idempotency_key=f"legacy:{receipt_id}",
                action=str(receipt.get("action") or "unknown"),
                previous_status=str(receipt.get("previous_status") or "todo"),
                current_status=current_status,
                previous_version=version - 1,
                current_version=version,
                accepted=bool(receipt.get("accepted", True)),
                receipt_json={**receipt, "receipt_id": str(receipt_id), "current_version": version},
            )
            self.session.add(model)
            run.status = current_status
        run.version = version
        await self.session.flush()


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _optional_uuid(value: Any) -> uuid.UUID | None:
    try:
        return _uuid(value)
    except (TypeError, ValueError):
        return None
