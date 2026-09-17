from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.errors import VersionConflictError
from interview_agent.learning.models import LearningGoalModel


class GoalService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def list(self) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(LearningGoalModel)
            .where(
                LearningGoalModel.tenant_id == self.tenant_id,
                LearningGoalModel.user_id == self.user_id,
            )
            .order_by(LearningGoalModel.updated_at.desc())
        )
        return [goal_to_dict(item) for item in result.scalars()]

    async def active(self) -> dict[str, Any] | None:
        items = await self.list()
        return next((item for item in items if item["status"] == "active"), items[0] if items else None)

    async def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.session.execute(
            select(LearningGoalModel).where(
                LearningGoalModel.tenant_id == self.tenant_id,
                LearningGoalModel.user_id == self.user_id,
                LearningGoalModel.status == "active",
            )
        )
        model = result.scalars().first()
        deadline = _date(payload.get("deadline"))
        if model is None:
            model = LearningGoalModel(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                title=str(payload["title"]),
                status="active",
            )
            self.session.add(model)
        else:
            expected = payload.get("expected_version")
            if expected is not None and int(expected) != model.version:
                raise VersionConflictError(expected=int(expected), current=model.version)
            statement = (
                update(LearningGoalModel)
                .where(
                    LearningGoalModel.id == model.id,
                    LearningGoalModel.version == model.version,
                )
                .values(version=model.version + 1)
            )
            changed = await self.session.execute(statement)
            if changed.rowcount != 1:
                await self.session.refresh(model)
                raise VersionConflictError(expected=int(expected or model.version), current=model.version)
            await self.session.refresh(model)
        model.title = str(payload["title"])
        model.target_role = str(payload.get("target_role") or "")
        model.deadline = deadline
        model.daily_minutes = int(payload.get("daily_minutes") or 30)
        model.success_criteria_json = dict(payload.get("success_criteria") or {})
        model.constraints_json = dict(payload.get("constraints") or {})
        await self.session.flush()
        return goal_to_dict(model)


def goal_to_dict(model: LearningGoalModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "title": model.title,
        "target_role": model.target_role,
        "deadline": model.deadline.isoformat() if model.deadline else None,
        "daily_minutes": model.daily_minutes,
        "status": model.status,
        "success_criteria": dict(model.success_criteria_json or {}),
        "constraints": dict(model.constraints_json or {}),
        "version": model.version,
        "updated_at": model.updated_at.isoformat(),
    }


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("deadline must be an ISO date") from exc
