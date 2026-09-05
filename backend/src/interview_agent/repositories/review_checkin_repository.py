"""复习打卡仓储：review_checkins 的 upsert/查询与 streak 连续段计算。"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import ReviewCheckinModel


class ReviewCheckinRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def get_checkin(
        self,
        plan_id: str | uuid.UUID,
        checkin_date: date,
    ) -> ReviewCheckinModel | None:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(ReviewCheckinModel).where(
                ReviewCheckinModel.tenant_id == self.tenant_id,
                ReviewCheckinModel.user_id == self.user_id,
                ReviewCheckinModel.plan_id == parsed,
                ReviewCheckinModel.checkin_date == checkin_date,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_checkin(
        self,
        plan_id: str | uuid.UUID,
        checkin_date: date,
        *,
        tasks_done: int,
        total_tasks: int,
        elapsed_minutes: int,
        note: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewCheckinModel:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        existing = await self.get_checkin(parsed, checkin_date)
        if existing is None:
            existing = ReviewCheckinModel(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                plan_id=parsed,
                checkin_date=checkin_date,
            )
            self.session.add(existing)
        existing.tasks_done = max(0, int(tasks_done))
        existing.total_tasks = max(0, int(total_tasks))
        existing.elapsed_minutes = max(0, int(elapsed_minutes))
        if note is not None:
            existing.note = note[:2000] if note else None
        if metadata is not None:
            existing.metadata_json = metadata
        await self.session.flush()
        return existing

    async def list_checkins(
        self,
        *,
        plan_id: str | uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ReviewCheckinModel]:
        filters = [
            ReviewCheckinModel.tenant_id == self.tenant_id,
            ReviewCheckinModel.user_id == self.user_id,
        ]
        if plan_id is not None:
            parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
            filters.append(ReviewCheckinModel.plan_id == parsed)
        if date_from is not None:
            filters.append(ReviewCheckinModel.checkin_date >= date_from)
        if date_to is not None:
            filters.append(ReviewCheckinModel.checkin_date <= date_to)
        result = await self.session.execute(
            select(ReviewCheckinModel)
            .where(*filters)
            .order_by(ReviewCheckinModel.checkin_date.asc())
        )
        return list(result.scalars().all())

    async def compute_streak(
        self,
        *,
        plan_id: str | uuid.UUID | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        from datetime import timedelta

        checkins = await self.list_checkins(plan_id=plan_id)
        dates = sorted({item.checkin_date for item in checkins if item.tasks_done > 0 or item.elapsed_minutes > 0})
        if not dates:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "total_checkin_days": 0,
                "last_checkin_date": None,
            }
        longest = 1
        run = 1
        for index in range(1, len(dates)):
            if dates[index] == dates[index - 1] + timedelta(days=1):
                run += 1
            else:
                run = 1
            longest = max(longest, run)

        reference = today or date.today()
        latest = dates[-1]
        current = 0
        if latest >= reference - timedelta(days=1):
            current = 1
            cursor = latest
            date_set = set(dates)
            while cursor - timedelta(days=1) in date_set:
                current += 1
                cursor -= timedelta(days=1)
        return {
            "current_streak": current,
            "longest_streak": longest,
            "total_checkin_days": len(dates),
            "last_checkin_date": latest.isoformat(),
        }


def checkin_to_dict(model: ReviewCheckinModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "plan_id": str(model.plan_id),
        "checkin_date": model.checkin_date.isoformat(),
        "tasks_done": model.tasks_done,
        "total_tasks": model.total_tasks,
        "elapsed_minutes": model.elapsed_minutes,
        "note": model.note,
        "metadata": dict(model.metadata_json or {}),
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }
