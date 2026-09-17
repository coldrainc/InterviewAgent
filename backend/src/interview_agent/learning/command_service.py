from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.errors import IdempotencyConflictError, VersionConflictError
from interview_agent.learning.observability import observe_learning_command
from interview_agent.learning.projector import infer_task_type, project_task
from interview_agent.learning.repository import LearningRepository
from interview_agent.learning.verifiers import VerificationResult, verifier_for
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.review_checkin_service import ReviewCheckinService


class LearningCommandService:
    def __init__(self, session: AsyncSession, *, tenant_id: str = "default", user_id: str = "anonymous") -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.repo = LearningRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.progress_repo = ReviewSiteRepository(session, tenant_id=tenant_id, user_id=user_id)

    async def task_view(self, task_id: str) -> dict[str, Any]:
        task = await self.repo.get_task(task_id)
        if task is None:
            raise LookupError("task not found")
        progress = await self.progress_repo.get_or_create_progress(task.id)
        run = await self.repo.get_or_create_run(task, progress)
        return project_task(task, progress, run=run, receipt=await self.repo.latest_receipt(run.id))

    @observe_learning_command
    async def execute(
        self,
        task_id: str,
        *,
        action: str,
        idempotency_key: str | None = None,
        expected_version: int | None = None,
        elapsed_minutes: int | None = None,
        mastery_score: int | None = None,
        note: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = action.strip().lower()
        if action not in {"start", "complete", "reopen", "verify"}:
            raise ValueError("action must be start, complete, reopen or verify")
        task = await self.repo.get_task(task_id)
        if task is None:
            raise LookupError("task not found")
        progress = await self.progress_repo.get_or_create_progress(task.id)
        run = await self.repo.get_or_create_run(task, progress)
        key = (idempotency_key or f"generated:{uuid.uuid4()}")[:128]
        existing = await self.repo.get_receipt_by_key(key)
        if existing is not None:
            if existing.task_id != task.id or existing.action != action:
                raise IdempotencyConflictError("idempotency key was already used for another command")
            return {
                "task": project_task(task, progress, run=run, receipt=existing),
                "receipt": existing.receipt_json,
                "idempotent_replay": True,
            }

        current_version = int(run.version or 0)
        if expected_version is not None and expected_version != current_version:
            raise VersionConflictError(expected=expected_version, current=current_version)
        previous_status = run.status
        verification, accepted, next_status = await self._transition(
            task, run, action=action, submitted=evidence or {}
        )
        now = datetime.now(timezone.utc)
        await self.repo.advance_run(
            run,
            expected_version=current_version,
            status=next_status,
            started_at=now if action == "start" else run.started_at,
            completed_at=now if next_status == "completed" else None,
        )
        verification_model = None
        if verification.status != "not_run":
            verification_model = await self.repo.add_verification(run, verification)
            if verification.evidence:
                source_id = next(iter(verification.evidence.values()), None)
                await self.repo.add_evidence(
                    run,
                    kind=infer_task_type(
                        link_type=task.link_type, simulation=bool(task.simulation), source=task.source
                    ),
                    source_type=verification.verifier,
                    source_id=str(source_id)[:128] if source_id else None,
                    payload=verification.evidence,
                )
        done = next_status == "completed"
        receipt = self._receipt(
            task=task,
            run=run,
            action=action,
            previous_status=previous_status,
            previous_version=current_version,
            accepted=accepted,
            verification=verification,
            done=done,
            occurred_at=now,
        )
        await self._write_legacy_progress(
            task,
            progress,
            receipt=receipt,
            done=done,
            elapsed_minutes=elapsed_minutes,
            mastery_score=mastery_score,
            note=note,
        )
        await self.repo.add_receipt(
            run,
            idempotency_key=key,
            action=action,
            previous_status=previous_status,
            previous_version=current_version,
            accepted=accepted,
            receipt=receipt,
            verification_id=verification_model.id if verification_model else None,
        )
        await ReviewCheckinService(
            self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).sync_day_checkin(progress.plan_id, progress.day_id)
        return {"task": project_task(task, progress, run=run), "receipt": receipt, "idempotent_replay": False}

    async def _transition(self, task, run, *, action: str, submitted: dict[str, Any]):
        if action == "start":
            result = VerificationResult("not_run", "none", "任务已开始")
            return result, True, "in_progress"
        if action == "reopen":
            result = VerificationResult("not_run", "manual", "任务已重新打开")
            return result, True, "todo"
        result = await verifier_for(
            task, self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).verify(task, run, submitted)
        return result, result.accepted, "completed" if result.accepted else "blocked"

    async def _write_legacy_progress(
        self, task, progress, *, receipt, done, elapsed_minutes, mastery_score, note
    ) -> None:
        metadata = dict(progress.metadata_json or {})
        harness = dict(metadata.get("learning_harness") or {})
        receipts = list(harness.get("receipts") or [])
        receipts.append(receipt)
        metadata["learning_harness"] = {
            **harness,
            "latest_receipt": receipt,
            "receipts": receipts[-20:],
            "ledger": "learning_effect_receipts",
        }
        await self.progress_repo.update_progress(
            task.id,
            {
                "done": done,
                "elapsed_minutes": elapsed_minutes if elapsed_minutes is not None else progress.elapsed_minutes,
                "mastery_score": mastery_score if mastery_score is not None else progress.mastery_score,
                "note": note if note is not None else progress.note,
                "metadata": metadata,
            },
        )

    def _receipt(
        self, *, task, run, action, previous_status, previous_version, accepted, verification, done, occurred_at
    ) -> dict[str, Any]:
        return {
            "receipt_id": str(uuid.uuid4()),
            "task_id": str(task.id),
            "run_id": str(run.id),
            "action": action,
            "accepted": accepted,
            "previous_status": previous_status,
            "current_status": run.status,
            "previous_version": previous_version,
            "current_version": run.version,
            "verification": verification.as_dict(),
            "evidence": verification.evidence,
            "next_action": self._next_action(task, accepted=accepted, done=done),
            "occurred_at": occurred_at.isoformat(),
        }

    @staticmethod
    def _next_action(task, *, accepted: bool, done: bool) -> dict[str, str] | None:
        if done:
            return {"command": "reopen", "label": "重新打开"}
        if not accepted:
            task_type = infer_task_type(
                link_type=task.link_type, simulation=bool(task.simulation), source=task.source
            )
            return {"command": "start", "label": {"interview": "继续模拟", "practice": "继续刷题"}.get(task_type, "继续任务")}
        return {"command": "complete", "label": "完成任务"}
