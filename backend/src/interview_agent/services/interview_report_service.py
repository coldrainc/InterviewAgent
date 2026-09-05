from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.core.config import InterviewConfig
from interview_agent.infrastructure.db.models import (
    ReviewDayModel,
    ReviewPlanModel,
    ReviewProgressModel,
    ReviewTaskModel,
)
from interview_agent.repositories.interview_report_repository import InterviewReportRepository


class InterviewReportService:
    """结构化面试报告的持久化、查询与薄弱项回流。"""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.repository = InterviewReportRepository(session, tenant_id=tenant_id, user_id=user_id)

    async def persist_evaluation(
        self,
        *,
        session_id: str,
        config: InterviewConfig,
        evaluation: dict,
    ) -> dict:
        payload = evaluation or {}
        model = await self.repository.upsert_report(
            session_id=session_id,
            mode=config.mode.value,
            total_score=_as_optional_int(payload.get("total_score")),
            dimension_scores=payload.get("dimension_scores") or {},
            per_question=payload.get("per_question") or [],
            evidence=payload.get("evidence") or [],
            strength_tags=payload.get("strength_tags") or [],
            weakness_tags=payload.get("weakness_tags") or [],
            suggestions=payload.get("suggestions") or [],
            summary_text=payload.get("summary") or None,
            report_version=str(payload.get("version") or "v1"),
            metadata_json={
                "verdict": payload.get("verdict"),
                "degraded": bool(payload.get("degraded", False)),
            },
        )
        return await self.repository.get_report(model.session_id)

    async def get_report(self, session_id: str) -> dict | None:
        return await self.repository.get_report(session_id)

    async def list_reports(self, limit: int = 20) -> dict:
        reports = await self.repository.list_reports(limit=limit)
        scores = [r["total_score"] for r in reports if isinstance(r.get("total_score"), int)]
        recent = scores[:5]
        trend = {
            "total_reports": len(reports),
            "scored_reports": len(scores),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "recent_average": round(sum(recent) / len(recent), 1) if recent else None,
            "latest_score": scores[0] if scores else None,
        }
        return {"reports": reports, "trend": trend}

    async def add_tasks_from_report(
        self,
        *,
        plan_id: str,
        session_id: str,
        max_items: int = 3,
    ) -> dict:
        """把报告的薄弱项/建议转成复习任务，写入最近一个未完成日。"""
        report = await self.repository.get_report(session_id)
        if report is None:
            raise LookupError("interview report not found")

        plan_uuid = uuid.UUID(str(plan_id))
        plan = await self.session.get(ReviewPlanModel, plan_uuid)
        if plan is None or plan.tenant_id != self.tenant_id or plan.user_id != self.user_id:
            raise LookupError("review plan not found")

        days_result = await self.session.execute(
            select(ReviewDayModel)
            .where(ReviewDayModel.plan_id == plan_uuid)
            .order_by(ReviewDayModel.sort_order.asc())
        )
        days = list(days_result.scalars().all())
        if not days:
            raise ValueError("review plan has no days")

        target_day = await self._pick_nearest_open_day(plan_uuid, days)

        suggestions = list(report.get("suggestions") or [])[:max_items]
        weakness_tags = report.get("weakness_tags") or []
        created: list[dict] = []
        existing_tasks = await self.session.execute(
            select(ReviewTaskModel.task_key).where(ReviewTaskModel.plan_id == plan_uuid)
        )
        existing_keys = {row[0] for row in existing_tasks.all()}

        index = 0
        for item in suggestions:
            title = (item.get("title") if isinstance(item, dict) else str(item)) or "薄弱项补强"
            detail = item.get("detail", "") if isinstance(item, dict) else ""
            category = item.get("category", "general") if isinstance(item, dict) else "general"
            index += 1
            task_key = f"report-{str(session_id)[:8]}-{index}"
            suffix = 1
            unique_key = task_key
            while unique_key in existing_keys:
                suffix += 1
                unique_key = f"{task_key}-{suffix}"
            tags = ["薄弱项回流"] + ([f"薄弱：{weakness_tags[0]}"] if weakness_tags else [])
            task = ReviewTaskModel(
                plan_id=plan_uuid,
                day_id=target_day.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                task_key=unique_key,
                title=title,
                tags_json=tags,
                critical=True,
                source="report",
                source_ref=str(session_id),
                link_type="interview",
                link_payload_json={"session_id": str(session_id), "category": category},
                reason=detail or title,
                sort_order=await self._next_task_sort_order(target_day.id),
            )
            self.session.add(task)
            existing_keys.add(unique_key)
            created.append(
                {
                    "task_key": unique_key,
                    "title": title,
                    "day_id": str(target_day.id),
                    "day_label": target_day.day_label,
                    "source": "report",
                    "link_type": "interview",
                }
            )
        await self.session.flush()
        return {
            "plan_id": str(plan_uuid),
            "day_id": str(target_day.id),
            "day_label": target_day.day_label,
            "created": created,
        }

    async def _pick_nearest_open_day(
        self, plan_uuid: uuid.UUID, days: list[ReviewDayModel]
    ) -> ReviewDayModel:
        """最早一个存在未完成任务的天；若全部完成则落在最后一天。"""
        tasks_result = await self.session.execute(
            select(ReviewTaskModel.id, ReviewTaskModel.day_id).where(
                ReviewTaskModel.plan_id == plan_uuid
            )
        )
        task_rows = tasks_result.all()
        task_ids_by_day: dict[uuid.UUID, list[uuid.UUID]] = {}
        for task_id, day_id in task_rows:
            task_ids_by_day.setdefault(day_id, []).append(task_id)

        done_task_ids: set[uuid.UUID] = set()
        all_task_ids = [tid for ids in task_ids_by_day.values() for tid in ids]
        if all_task_ids:
            progress_result = await self.session.execute(
                select(ReviewProgressModel.task_id).where(
                    ReviewProgressModel.tenant_id == self.tenant_id,
                    ReviewProgressModel.user_id == self.user_id,
                    ReviewProgressModel.plan_id == plan_uuid,
                    ReviewProgressModel.done.is_(True),
                )
            )
            done_task_ids = {row[0] for row in progress_result.all()}

        for day in days:
            day_task_ids = task_ids_by_day.get(day.id, [])
            if day_task_ids and any(tid not in done_task_ids for tid in day_task_ids):
                return day
        return days[-1]

    async def _next_task_sort_order(self, day_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(ReviewTaskModel.sort_order)
            .where(ReviewTaskModel.day_id == day_id)
            .order_by(ReviewTaskModel.sort_order.desc())
            .limit(1)
        )
        row = result.first()
        return (row[0] + 1) if row else 1


def _as_optional_int(value) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
