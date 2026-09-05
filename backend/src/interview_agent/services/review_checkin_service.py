"""复习打卡服务：今日任务、打卡 upsert（幂等）、进度变更同步聚合、streak。"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.repositories.review_checkin_repository import (
    ReviewCheckinRepository,
    checkin_to_dict,
)
from interview_agent.repositories.review_site_repository import ReviewSiteRepository


class ReviewCheckinService:
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
        self.repo = ReviewSiteRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.checkin_repo = ReviewCheckinRepository(session, tenant_id=tenant_id, user_id=user_id)

    async def get_today(self, plan_id: str, *, today: date | None = None) -> dict[str, Any]:
        plan = await self.repo.get_plan(plan_id)
        if plan is None:
            raise LookupError("plan not found")
        target = today or date.today()
        response: dict[str, Any] = {
            "plan_id": str(plan.id),
            "date": target.isoformat(),
            "active": plan.status == "active",
            "status": plan.status,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "day": None,
            "tasks": [],
            "summary": {"tasks_done": 0, "total_tasks": 0, "elapsed_minutes": 0},
            "checkin": None,
        }
        if plan.status != "active" or not plan.start_date:
            return response

        days = await self.repo.list_days(plan.id, with_tasks=True)
        day = await self._day_for_date(plan, days, target)
        checkin = await self.checkin_repo.get_checkin(plan.id, target)
        response["checkin"] = checkin_to_dict(checkin) if checkin else None
        if day is None:
            return response

        tasks, done_map, tasks_done, total_tasks, elapsed = await self._aggregate_day(plan.id, day)
        response["day"] = {
            "id": str(day.id),
            "day_key": day.day_key,
            "day_label": day.day_label,
            "title": day.title,
            "scheduled_date": day.scheduled_date.isoformat() if day.scheduled_date else None,
            "sort_order": day.sort_order,
        }
        response["tasks"] = [
            {
                "id": str(task.id),
                "task_key": task.task_key,
                "title": task.title,
                "sort_order": task.sort_order,
                "critical": bool(task.critical),
                "tags": list(task.tags_json or []),
                "done": bool(done_map[task.id].done) if task.id in done_map else False,
                "elapsed_minutes": int(done_map[task.id].elapsed_minutes or 0) if task.id in done_map else 0,
                "mastery_score": done_map[task.id].mastery_score if task.id in done_map else None,
            }
            for task in tasks
        ]
        response["summary"] = {
            "tasks_done": tasks_done,
            "total_tasks": total_tasks,
            "elapsed_minutes": elapsed,
        }
        return response

    async def checkin(
        self,
        plan_id: str,
        *,
        elapsed_minutes: int | None = None,
        note: str | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        plan = await self.repo.get_plan(plan_id)
        if plan is None:
            raise LookupError("plan not found")
        if plan.status != "active":
            raise ValueError("plan is not active")
        target = today or date.today()

        tasks_done = 0
        total_tasks = 0
        progress_elapsed = 0
        days = await self.repo.list_days(plan.id, with_tasks=True)
        day = await self._day_for_date(plan, days, target)
        if day is not None:
            _, _, tasks_done, total_tasks, progress_elapsed = await self._aggregate_day(plan.id, day)

        existing = await self.checkin_repo.get_checkin(plan.id, target)
        manual_minutes = 0
        if existing and existing.metadata_json:
            manual_minutes = int(existing.metadata_json.get("manual_elapsed_minutes") or 0)
        if elapsed_minutes:
            manual_minutes += max(0, int(elapsed_minutes))

        model = await self.checkin_repo.upsert_checkin(
            plan.id,
            target,
            tasks_done=tasks_done,
            total_tasks=total_tasks,
            elapsed_minutes=progress_elapsed + manual_minutes,
            note=note,
            metadata={"manual_elapsed_minutes": manual_minutes},
        )
        streak = await self.checkin_repo.compute_streak(plan_id=plan.id, today=target)
        return {"checkin": checkin_to_dict(model), "streak": streak}

    async def sync_day_checkin(
        self,
        plan_id: str | uuid.UUID,
        day_id: str | uuid.UUID,
        *,
        today: date | None = None,
    ) -> dict[str, Any] | None:
        """任务进度变更后同步当日 checkin 聚合（非当天/计划未激活则跳过）。"""
        plan = await self.repo.get_plan(plan_id)
        if plan is None or plan.status != "active" or not plan.start_date:
            return None
        target = today or date.today()
        days = await self.repo.list_days(plan.id, with_tasks=True)
        parsed_day = day_id if isinstance(day_id, uuid.UUID) else uuid.UUID(str(day_id))
        day = next((item for item in days if item.id == parsed_day), None)
        if day is None:
            return None
        if day.scheduled_date is not None and day.scheduled_date != target:
            return None
        if day.scheduled_date is None:
            scheduled_day = await self._day_for_date(plan, days, target)
            if scheduled_day is None or scheduled_day.id != day.id:
                return None

        _, _, tasks_done, total_tasks, progress_elapsed = await self._aggregate_day(plan.id, day)
        existing = await self.checkin_repo.get_checkin(plan.id, target)
        manual_minutes = 0
        note = None
        if existing:
            manual_minutes = int((existing.metadata_json or {}).get("manual_elapsed_minutes") or 0)
            note = existing.note
        model = await self.checkin_repo.upsert_checkin(
            plan.id,
            target,
            tasks_done=tasks_done,
            total_tasks=total_tasks,
            elapsed_minutes=progress_elapsed + manual_minutes,
            note=note,
            metadata={"manual_elapsed_minutes": manual_minutes},
        )
        return checkin_to_dict(model)

    async def list_checkins(
        self,
        *,
        plan_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        items = await self.checkin_repo.list_checkins(
            plan_id=plan_id, date_from=date_from, date_to=date_to
        )
        streak = await self.checkin_repo.compute_streak(plan_id=plan_id, today=today)
        return {"checkins": [checkin_to_dict(item) for item in items], "streak": streak}

    async def _day_for_date(self, plan, days: list, target: date):
        for day in days:
            if day.scheduled_date == target:
                return day
        if plan.start_date:
            ordered = sorted(days, key=lambda d: d.sort_order)
            index = (target - plan.start_date).days
            if 0 <= index < len(ordered):
                return ordered[index]
        return None

    async def _aggregate_day(self, plan_id, day) -> tuple[list, dict, int, int, int]:
        progresses = await self.repo.list_progresses(plan_id, day.id)
        done_map = {progress.task_id: progress for progress in progresses}
        tasks = sorted(day.tasks or [], key=lambda t: t.sort_order)
        tasks_done = sum(1 for task in tasks if done_map.get(task.id) and done_map[task.id].done)
        elapsed = sum(int(progress.elapsed_minutes or 0) for progress in progresses)
        return tasks, done_map, tasks_done, len(tasks), elapsed
