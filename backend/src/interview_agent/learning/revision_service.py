from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.models import LearningPlanRevisionModel, LearningTaskRunModel
from interview_agent.learning.revision_policy import RevisionPolicy
from interview_agent.repositories.review_site_repository import ReviewSiteRepository


class RevisionService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.plans = ReviewSiteRepository(session, tenant_id=tenant_id, user_id=user_id)

    async def propose(self, plan_id: str, *, daily_minutes: int, dimensions: dict) -> dict[str, Any] | None:
        plan = await self.plans.get_plan(plan_id)
        if plan is None:
            raise LookupError("plan not found")
        tasks = [task for day in plan.days for task in day.tasks]
        result = await self.session.execute(
            select(LearningTaskRunModel).where(
                LearningTaskRunModel.tenant_id == self.tenant_id,
                LearningTaskRunModel.user_id == self.user_id,
                LearningTaskRunModel.plan_id == plan.id,
            )
        )
        runs = {item.task_id: item for item in result.scalars()}
        proposal = RevisionPolicy().propose(
            tasks=tasks, runs=runs, daily_minutes=daily_minutes, dimensions=dimensions
        )
        if proposal is None:
            return None
        model = LearningPlanRevisionModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            plan_id=plan.id,
            reason=proposal.reason,
            trigger_json=proposal.trigger,
            diff_json=proposal.diff,
        )
        self.session.add(model)
        await self.session.flush()
        return revision_to_dict(model)

    async def decide(self, revision_id: str, action: str) -> dict[str, Any]:
        model = await self._get(revision_id)
        if model is None:
            raise LookupError("revision not found")
        now = datetime.now(timezone.utc)
        if action == "apply":
            if model.status not in {"proposed", "reverted"}:
                raise ValueError("revision cannot be applied")
            await self._set_deferred(model, True)
            model.status = "applied"
            model.applied_at = now
            model.reverted_at = None
        elif action == "revert":
            if model.status != "applied" or not model.reversible:
                raise ValueError("revision cannot be reverted")
            await self._set_deferred(model, False)
            model.status = "reverted"
            model.reverted_at = now
        else:
            raise ValueError("action must be apply or revert")
        await self.session.flush()
        return revision_to_dict(model)

    async def list(self, plan_id: str) -> list[dict[str, Any]]:
        plan = await self.plans.get_plan(plan_id)
        if plan is None:
            raise LookupError("plan not found")
        result = await self.session.execute(
            select(LearningPlanRevisionModel)
            .where(
                LearningPlanRevisionModel.plan_id == plan.id,
                LearningPlanRevisionModel.tenant_id == self.tenant_id,
                LearningPlanRevisionModel.user_id == self.user_id,
            )
            .order_by(LearningPlanRevisionModel.created_at.desc())
        )
        return [revision_to_dict(item) for item in result.scalars()]

    async def _get(self, revision_id: str):
        result = await self.session.execute(
            select(LearningPlanRevisionModel).where(
                LearningPlanRevisionModel.id == uuid.UUID(revision_id),
                LearningPlanRevisionModel.tenant_id == self.tenant_id,
                LearningPlanRevisionModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _set_deferred(self, model, deferred: bool) -> None:
        for task_id in model.diff_json.get("defer_task_ids") or []:
            task = await self.plans.get_task(task_id)
            if task is None or bool((task.link_payload_json or {}).get("locked")):
                continue
            payload = dict(task.link_payload_json or {})
            payload["deferred"] = deferred
            payload["revision_id"] = str(model.id) if deferred else None
            task.link_payload_json = payload


def revision_to_dict(model: LearningPlanRevisionModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "plan_id": str(model.plan_id),
        "status": model.status,
        "reason": model.reason,
        "trigger": dict(model.trigger_json or {}),
        "diff": dict(model.diff_json or {}),
        "reversible": model.reversible,
        "created_at": model.created_at.isoformat(),
    }
