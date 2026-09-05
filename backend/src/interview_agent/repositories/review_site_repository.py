from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from interview_agent.domain.review_site import DEFAULT_REVIEW_SITE
from interview_agent.infrastructure.db.models import (
    A4MemoryItemModel,
    IntroScriptModel,
    ReviewDayModel,
    ReviewPhaseModel,
    ReviewPlanModel,
    ReviewProgressModel,
    ReviewTaskModel,
    StarCardModel,
    utcnow,
)


class ReviewSiteRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def list_plans(self, include_archived: bool = False) -> list[ReviewPlanModel]:
        filters = [
            ReviewPlanModel.tenant_id == self.tenant_id,
            ReviewPlanModel.user_id == self.user_id,
        ]
        if not include_archived:
            filters.append(ReviewPlanModel.status != "archived")
        result = await self.session.execute(
            select(ReviewPlanModel)
            .where(*filters)
            .order_by(ReviewPlanModel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_plan(self, plan_id: str | uuid.UUID) -> ReviewPlanModel | None:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(ReviewPlanModel)
            .options(
                selectinload(ReviewPlanModel.phases),
                selectinload(ReviewPlanModel.days).selectinload(ReviewDayModel.tasks),
                selectinload(ReviewPlanModel.progress_records),
                selectinload(ReviewPlanModel.intro_scripts),
                selectinload(ReviewPlanModel.star_cards),
                selectinload(ReviewPlanModel.a4_memory),
            )
            .where(
                ReviewPlanModel.tenant_id == self.tenant_id,
                ReviewPlanModel.user_id == self.user_id,
                ReviewPlanModel.id == parsed,
            )
        )
        return result.scalar_one_or_none()

    async def get_plan_by_key(self, plan_key: str) -> ReviewPlanModel | None:
        result = await self.session.execute(
            select(ReviewPlanModel)
            .options(
                selectinload(ReviewPlanModel.phases),
                selectinload(ReviewPlanModel.days).selectinload(ReviewDayModel.tasks),
                selectinload(ReviewPlanModel.progress_records),
                selectinload(ReviewPlanModel.intro_scripts),
                selectinload(ReviewPlanModel.star_cards),
                selectinload(ReviewPlanModel.a4_memory),
            )
            .where(
                ReviewPlanModel.tenant_id == self.tenant_id,
                ReviewPlanModel.user_id == self.user_id,
                ReviewPlanModel.plan_key == plan_key,
            )
        )
        return result.scalar_one_or_none()

    async def create_plan(
        self,
        plan_data: dict[str, Any],
        phases: list[dict[str, Any]],
        days: list[dict[str, Any]],
        tasks_per_day: dict[str, list[dict[str, Any]]],
        intro_scripts: list[dict[str, Any]],
        star_cards: list[dict[str, Any]],
        a4_memory: list[dict[str, Any]],
    ) -> ReviewPlanModel:
        plan = ReviewPlanModel(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            plan_key=str(plan_data.get("plan_key") or ""),
            title=str(plan_data.get("title") or ""),
            subtitle=str(plan_data.get("subtitle") or ""),
            description=str(plan_data.get("description") or ""),
            status=str(plan_data.get("status") or "draft"),
            source_root=str(plan_data.get("source_root") or ""),
            source_documents_json=_safe_list(plan_data.get("source_documents")),
            commercial_positioning_json=_safe_list(plan_data.get("commercial_positioning")),
            metadata_json=_safe_dict(plan_data.get("metadata")),
        )
        self.session.add(plan)
        await self.session.flush()

        for idx, phase_data in enumerate(phases):
            self.session.add(ReviewPhaseModel(
                id=uuid.uuid4(),
                plan_id=plan.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                phase_key=str(phase_data.get("id") or phase_data.get("phase_key") or f"p{idx+1}"),
                title=str(phase_data.get("title") or ""),
                range_label=str(phase_data.get("range") or phase_data.get("range_label") or ""),
                goal=str(phase_data.get("goal") or ""),
                sort_order=idx,
            ))

        day_model_map: dict[str, ReviewDayModel] = {}
        for day_idx, day_data in enumerate(days):
            day_key = str(day_data.get("id") or day_data.get("day_key") or f"day-{day_idx+1}")
            day_model = ReviewDayModel(
                id=uuid.uuid4(),
                plan_id=plan.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                day_key=day_key,
                day_label=str(day_data.get("day") or day_data.get("day_label") or ""),
                phase_key=str(day_data.get("phase") or day_data.get("phase_key") or ""),
                title=str(day_data.get("title") or ""),
                acceptance=str(day_data.get("acceptance") or "") or None,
                scheduled_date=_parse_date(day_data.get("scheduled_date")),
                sort_order=day_idx,
            )
            self.session.add(day_model)
            day_model_map[day_key] = day_model

        await self.session.flush()

        for day_key, tasks in tasks_per_day.items():
            day_model = day_model_map.get(day_key)
            if not day_model:
                continue
            for task_idx, task_data in enumerate(tasks):
                self.session.add(ReviewTaskModel(
                    id=uuid.uuid4(),
                    plan_id=plan.id,
                    day_id=day_model.id,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    task_key=str(task_data.get("id") or task_data.get("task_key") or f"{day_key}-t{task_idx+1}"),
                    title=str(task_data.get("title") or ""),
                    tags_json=_safe_list(task_data.get("tags")),
                    critical=bool(task_data.get("critical", False)),
                    simulation=bool(task_data.get("simulation", False)),
                    docs_json=_safe_list(task_data.get("docs")),
                    reason=str(task_data.get("reason") or "") or None,
                    source=str(task_data.get("source") or "plan")[:32],
                    source_ref=str(task_data.get("source_ref") or "")[:255] or None,
                    link_type=str(task_data.get("link_type") or "none")[:32],
                    link_payload_json=_safe_dict(task_data.get("link_payload")),
                    sort_order=task_idx,
                ))

        for idx, item in enumerate(intro_scripts):
            self.session.add(IntroScriptModel(
                id=uuid.uuid4(),
                plan_id=plan.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                script_key=str(item.get("id") or item.get("script_key") or f"intro-{idx+1}"),
                label=str(item.get("label") or ""),
                duration_seconds=int(item.get("duration_seconds") or 0),
                scenario=str(item.get("scenario") or ""),
                text=str(item.get("text") or ""),
                sort_order=idx,
            ))

        for idx, item in enumerate(star_cards):
            self.session.add(StarCardModel(
                id=uuid.uuid4(),
                plan_id=plan.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                card_key=str(item.get("id") or item.get("card_key") or f"star-{idx+1}"),
                title=str(item.get("title") or ""),
                tag=str(item.get("tag") or ""),
                background=str(item.get("background") or ""),
                challenge=str(item.get("challenge") or ""),
                solution=str(item.get("solution") or ""),
                result=str(item.get("result") or ""),
                sort_order=idx,
            ))

        for idx, item in enumerate(a4_memory):
            content = item if isinstance(item, str) else str(item.get("content") or "")
            side = "ALL" if isinstance(item, str) else str(item.get("side") or "ALL")
            self.session.add(A4MemoryItemModel(
                id=uuid.uuid4(),
                plan_id=plan.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                content=content,
                side=side,
                sort_order=idx,
            ))

        await self.session.flush()
        return plan

    async def update_plan(self, plan_id: str | uuid.UUID, data: dict[str, Any]) -> ReviewPlanModel | None:
        plan = await self.get_plan(plan_id)
        if not plan:
            return None
        for field in ("title", "subtitle", "description", "status", "source_root"):
            if field in data and data[field] is not None:
                setattr(plan, field, str(data[field]))
        if "source_documents" in data:
            plan.source_documents_json = _safe_list(data["source_documents"])
        if "commercial_positioning" in data:
            plan.commercial_positioning_json = _safe_list(data["commercial_positioning"])
        if "metadata" in data:
            plan.metadata_json = _safe_dict(data["metadata"])
        if plan.status == "active" and plan.start_date is None:
            start_date = _parse_date(data.get("start_date")) or date.today()
            await self.schedule_plan_days(plan, start_date)
        await self.session.flush()
        return plan

    async def schedule_plan_days(
        self,
        plan: ReviewPlanModel,
        start_date: date,
    ) -> ReviewPlanModel:
        """激活计划：写 start_date，并给每天排 scheduled_date = start_date + day_index。"""
        plan.start_date = start_date
        days = await self.list_days(plan.id, with_tasks=False)
        for index, day in enumerate(sorted(days, key=lambda d: d.sort_order)):
            if day.scheduled_date is None:
                day.scheduled_date = start_date + timedelta(days=index)
        await self.session.flush()
        return plan

    async def archive_plan(self, plan_id: str | uuid.UUID) -> ReviewPlanModel | None:
        return await self.update_plan(plan_id, {"status": "archived"})

    async def list_phases(self, plan_id: str | uuid.UUID) -> list[ReviewPhaseModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(ReviewPhaseModel)
            .where(
                ReviewPhaseModel.plan_id == parsed,
                ReviewPhaseModel.tenant_id == self.tenant_id,
                ReviewPhaseModel.user_id == self.user_id,
            )
            .order_by(ReviewPhaseModel.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_days(self, plan_id: str | uuid.UUID, with_tasks: bool = True) -> list[ReviewDayModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        stmt = select(ReviewDayModel).where(
            ReviewDayModel.plan_id == parsed,
            ReviewDayModel.tenant_id == self.tenant_id,
            ReviewDayModel.user_id == self.user_id,
        )
        if with_tasks:
            stmt = stmt.options(selectinload(ReviewDayModel.tasks))
        stmt = stmt.order_by(ReviewDayModel.sort_order.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_task(self, task_id: str | uuid.UUID) -> ReviewTaskModel | None:
        parsed = task_id if isinstance(task_id, uuid.UUID) else uuid.UUID(str(task_id))
        result = await self.session.execute(
            select(ReviewTaskModel).options(joinedload(ReviewTaskModel.day)).where(
                ReviewTaskModel.id == parsed,
                ReviewTaskModel.tenant_id == self.tenant_id,
                ReviewTaskModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_day(self, day_id: str | uuid.UUID) -> ReviewDayModel | None:
        parsed = day_id if isinstance(day_id, uuid.UUID) else uuid.UUID(str(day_id))
        result = await self.session.execute(
            select(ReviewDayModel).where(
                ReviewDayModel.id == parsed,
                ReviewDayModel.tenant_id == self.tenant_id,
                ReviewDayModel.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_day(self, plan_id: str | uuid.UUID, data: dict[str, Any]) -> ReviewDayModel | None:
        plan = await self.get_plan(plan_id)
        if not plan:
            return None
        days = await self.list_days(plan_id, with_tasks=False)
        next_sort = max((day.sort_order for day in days), default=-1) + 1
        model = ReviewDayModel(
            id=uuid.uuid4(),
            plan_id=plan.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            day_key=str(data.get("day_key") or f"day-{next_sort + 1}"),
            day_label=str(data.get("day_label") or data.get("day") or f"Day {next_sort + 1}"),
            phase_key=str(data.get("phase_key") or data.get("phase") or ""),
            title=str(data.get("title") or ""),
            acceptance=str(data.get("acceptance") or "") or None,
            scheduled_date=_parse_date(data.get("scheduled_date")),
            sort_order=int(data.get("sort_order") if data.get("sort_order") is not None else next_sort),
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def update_day(self, day_id: str | uuid.UUID, data: dict[str, Any]) -> ReviewDayModel | None:
        day = await self.get_day(day_id)
        if not day:
            return None
        for field in ("day_key", "day_label", "phase_key", "title"):
            if data.get(field) is not None:
                setattr(day, field, str(data[field]))
        if "acceptance" in data:
            day.acceptance = str(data["acceptance"]) if data["acceptance"] else None
        if "scheduled_date" in data:
            day.scheduled_date = _parse_date(data.get("scheduled_date"))
        if data.get("sort_order") is not None:
            day.sort_order = int(data["sort_order"])
        await self.session.flush()
        return day

    async def delete_day(self, day_id: str | uuid.UUID) -> bool:
        day = await self.get_day(day_id)
        if not day:
            return False
        tasks = await self.session.execute(
            select(ReviewTaskModel).where(ReviewTaskModel.day_id == day.id)
        )
        task_ids = [task.id for task in tasks.scalars().all()]
        if task_ids:
            progresses = await self.session.execute(
                select(ReviewProgressModel).where(ReviewProgressModel.task_id.in_(task_ids))
            )
            for progress in progresses.scalars().all():
                await self.session.delete(progress)
            for task_id in task_ids:
                task_result = await self.session.get(ReviewTaskModel, task_id)
                if task_result:
                    await self.session.delete(task_result)
        await self.session.delete(day)
        await self.session.flush()
        return True

    async def create_task(self, day_id: str | uuid.UUID, data: dict[str, Any]) -> ReviewTaskModel | None:
        day = await self.get_day(day_id)
        if not day:
            return None
        tasks_result = await self.session.execute(
            select(ReviewTaskModel).where(ReviewTaskModel.day_id == day.id)
        )
        existing_tasks = tasks_result.scalars().all()
        next_sort = max((task.sort_order for task in existing_tasks), default=-1) + 1
        model = ReviewTaskModel(
            id=uuid.uuid4(),
            plan_id=day.plan_id,
            day_id=day.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            task_key=str(data.get("task_key") or f"day-{day.sort_order}-t-{next_sort + 1}"),
            title=str(data.get("title") or ""),
            tags_json=_safe_list(data.get("tags")),
            critical=bool(data.get("critical", False)),
            simulation=bool(data.get("simulation", False)),
            docs_json=_safe_list(data.get("docs")),
            reason=str(data.get("reason") or "") or None,
            source=str(data.get("source") or "manual")[:32],
            source_ref=str(data.get("source_ref") or "")[:255] or None,
            link_type=str(data.get("link_type") or "none")[:32],
            link_payload_json=_safe_dict(data.get("link_payload")),
            sort_order=int(data.get("sort_order") if data.get("sort_order") is not None else next_sort),
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def update_task(self, task_id: str | uuid.UUID, data: dict[str, Any]) -> ReviewTaskModel | None:
        task = await self.get_task(task_id)
        if not task:
            return None
        for field in ("task_key", "title", "reason", "source", "source_ref", "link_type"):
            if data.get(field) is not None:
                setattr(task, field, str(data[field]))
        if data.get("tags") is not None:
            task.tags_json = _safe_list(data["tags"])
        if data.get("docs") is not None:
            task.docs_json = _safe_list(data["docs"])
        if data.get("link_payload") is not None:
            task.link_payload_json = _safe_dict(data["link_payload"])
        if data.get("critical") is not None:
            task.critical = bool(data["critical"])
        if data.get("simulation") is not None:
            task.simulation = bool(data["simulation"])
        if data.get("sort_order") is not None:
            task.sort_order = int(data["sort_order"])
        await self.session.flush()
        return task

    async def delete_task(self, task_id: str | uuid.UUID) -> bool:
        task = await self.get_task(task_id)
        if not task:
            return False
        progresses = await self.session.execute(
            select(ReviewProgressModel).where(ReviewProgressModel.task_id == task.id)
        )
        for progress in progresses.scalars().all():
            await self.session.delete(progress)
        await self.session.delete(task)
        await self.session.flush()
        return True

    async def upsert_material_item(
        self,
        plan_id: str | uuid.UUID,
        kind: str,
        data: dict[str, Any],
        item_id: str | uuid.UUID | None = None,
    ):
        plan = await self.get_plan(plan_id)
        if not plan:
            return None
        model = None
        if item_id is not None:
            model = await self.get_material_item(kind, item_id)
        if model is None:
            if kind == "intro_scripts":
                model = IntroScriptModel(id=uuid.uuid4(), plan_id=plan.id, tenant_id=self.tenant_id, user_id=self.user_id)
            elif kind == "star_cards":
                model = StarCardModel(id=uuid.uuid4(), plan_id=plan.id, tenant_id=self.tenant_id, user_id=self.user_id)
            elif kind == "a4_memory":
                model = A4MemoryItemModel(id=uuid.uuid4(), plan_id=plan.id, tenant_id=self.tenant_id, user_id=self.user_id)
            else:
                raise ValueError(f"unknown material kind: {kind}")
            self.session.add(model)
        if kind == "intro_scripts":
            model.script_key = str(data.get("script_key") or data.get("id") or model.script_key or f"intro-{uuid.uuid4().hex[:6]}")
            model.label = str(data.get("label") or "")
            model.duration_seconds = int(data.get("duration_seconds") or 0)
            model.scenario = str(data.get("scenario") or "")
            if data.get("text") is not None:
                model.text = str(data["text"])
            if data.get("sort_order") is not None:
                model.sort_order = int(data["sort_order"])
        elif kind == "star_cards":
            model.card_key = str(data.get("card_key") or data.get("id") or model.card_key or f"star-{uuid.uuid4().hex[:6]}")
            for field in ("title", "tag", "background", "challenge", "solution", "result"):
                if data.get(field) is not None:
                    setattr(model, field, str(data[field]))
            if data.get("sort_order") is not None:
                model.sort_order = int(data["sort_order"])
        else:
            if data.get("content") is not None:
                model.content = str(data["content"])
            model.side = str(data.get("side") or "ALL")
            if data.get("sort_order") is not None:
                model.sort_order = int(data["sort_order"])
        await self.session.flush()
        return model

    async def get_material_item(self, kind: str, item_id: str | uuid.UUID):
        parsed = item_id if isinstance(item_id, uuid.UUID) else uuid.UUID(str(item_id))
        model_map = {
            "intro_scripts": IntroScriptModel,
            "star_cards": StarCardModel,
            "a4_memory": A4MemoryItemModel,
        }
        model_cls = model_map.get(kind)
        if model_cls is None:
            raise ValueError(f"unknown material kind: {kind}")
        result = await self.session.execute(
            select(model_cls).where(
                model_cls.id == parsed,
                model_cls.tenant_id == self.tenant_id,
                model_cls.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_material_item(self, kind: str, item_id: str | uuid.UUID) -> bool:
        model = await self.get_material_item(kind, item_id)
        if not model:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def get_or_create_progress(self, task_id: str | uuid.UUID) -> ReviewProgressModel:
        parsed = task_id if isinstance(task_id, uuid.UUID) else uuid.UUID(str(task_id))
        result = await self.session.execute(
            select(ReviewProgressModel).where(
                ReviewProgressModel.tenant_id == self.tenant_id,
                ReviewProgressModel.user_id == self.user_id,
                ReviewProgressModel.task_id == parsed,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        task = await self.get_task(task_id)
        if not task:
            raise ValueError("task not found")
        new = ReviewProgressModel(
            id=uuid.uuid4(),
            plan_id=task.plan_id,
            day_id=task.day_id,
            task_id=task.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        self.session.add(new)
        await self.session.flush()
        return new

    async def update_progress(
        self,
        task_id: str | uuid.UUID,
        data: dict[str, Any],
    ) -> ReviewProgressModel:
        progress = await self.get_or_create_progress(task_id)
        if "done" in data and data["done"] is not None:
            progress.done = bool(data["done"])
            if progress.done and progress.done_at is None:
                progress.done_at = utcnow()
            if not progress.done:
                progress.done_at = None
        if "note" in data:
            progress.note = str(data["note"]) if data["note"] is not None else None
        if "elapsed_minutes" in data:
            val = data["elapsed_minutes"]
            progress.elapsed_minutes = int(val) if val is not None else None
        if "mastery_score" in data:
            val = data["mastery_score"]
            if val is None:
                progress.mastery_score = None
            else:
                progress.mastery_score = max(0, min(5, int(val)))
        if "metadata" in data:
            progress.metadata_json = _safe_dict(data["metadata"])
        await self.session.flush()
        return progress

    async def list_progresses(
        self,
        plan_id: str | uuid.UUID,
        day_id: str | uuid.UUID | None = None,
    ) -> list[ReviewProgressModel]:
        parsed_plan = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        filters = [
            ReviewProgressModel.plan_id == parsed_plan,
            ReviewProgressModel.tenant_id == self.tenant_id,
            ReviewProgressModel.user_id == self.user_id,
        ]
        if day_id is not None:
            parsed_day = day_id if isinstance(day_id, uuid.UUID) else uuid.UUID(str(day_id))
            filters.append(ReviewProgressModel.day_id == parsed_day)
        result = await self.session.execute(select(ReviewProgressModel).where(*filters))
        return list(result.scalars().all())

    async def list_intro_scripts(self, plan_id: str | uuid.UUID) -> list[IntroScriptModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(IntroScriptModel)
            .where(
                IntroScriptModel.plan_id == parsed,
                IntroScriptModel.tenant_id == self.tenant_id,
                IntroScriptModel.user_id == self.user_id,
            )
            .order_by(IntroScriptModel.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_star_cards(self, plan_id: str | uuid.UUID) -> list[StarCardModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(StarCardModel)
            .where(
                StarCardModel.plan_id == parsed,
                StarCardModel.tenant_id == self.tenant_id,
                StarCardModel.user_id == self.user_id,
            )
            .order_by(StarCardModel.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_a4_memory(self, plan_id: str | uuid.UUID) -> list[A4MemoryItemModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        result = await self.session.execute(
            select(A4MemoryItemModel)
            .where(
                A4MemoryItemModel.plan_id == parsed,
                A4MemoryItemModel.tenant_id == self.tenant_id,
                A4MemoryItemModel.user_id == self.user_id,
            )
            .order_by(A4MemoryItemModel.sort_order.asc())
        )
        return list(result.scalars().all())

    async def upsert_intro_scripts(
        self,
        plan_id: str | uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[IntroScriptModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        existing = {m.script_key: m for m in await self.list_intro_scripts(plan_id)}
        output: list[IntroScriptModel] = []
        for idx, data in enumerate(items):
            key = str(data.get("id") or data.get("script_key") or f"intro-{idx+1}")
            model = existing.get(key)
            if model is None:
                model = IntroScriptModel(
                    id=uuid.uuid4(),
                    plan_id=parsed,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    script_key=key,
                )
                self.session.add(model)
            model.label = str(data.get("label", model.label) or "")
            model.duration_seconds = int(data.get("duration_seconds", model.duration_seconds) or 0)
            model.scenario = str(data.get("scenario", model.scenario) or "")
            model.text = str(data.get("text", model.text) or "")
            model.sort_order = idx
            output.append(model)
        await self.session.flush()
        return output

    async def upsert_star_cards(
        self,
        plan_id: str | uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[StarCardModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        existing = {m.card_key: m for m in await self.list_star_cards(plan_id)}
        output: list[StarCardModel] = []
        for idx, data in enumerate(items):
            key = str(data.get("id") or data.get("card_key") or f"star-{idx+1}")
            model = existing.get(key)
            if model is None:
                model = StarCardModel(
                    id=uuid.uuid4(),
                    plan_id=parsed,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    card_key=key,
                )
                self.session.add(model)
            for field in ("title", "tag", "background", "challenge", "solution", "result"):
                if field in data:
                    setattr(model, field, str(data[field] or ""))
            model.sort_order = idx
            output.append(model)
        await self.session.flush()
        return output

    async def upsert_a4_memory(
        self,
        plan_id: str | uuid.UUID,
        items: list[Any],
    ) -> list[A4MemoryItemModel]:
        parsed = plan_id if isinstance(plan_id, uuid.UUID) else uuid.UUID(str(plan_id))
        current = await self.list_a4_memory(plan_id)
        for m in current:
            await self.session.delete(m)
        await self.session.flush()
        output: list[A4MemoryItemModel] = []
        for idx, item in enumerate(items):
            content = item if isinstance(item, str) else str(item.get("content") or "")
            side = "ALL" if isinstance(item, str) else str(item.get("side") or "ALL")
            model = A4MemoryItemModel(
                id=uuid.uuid4(),
                plan_id=parsed,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                content=content,
                side=side,
                sort_order=idx,
            )
            self.session.add(model)
            output.append(model)
        await self.session.flush()
        return output

    async def seed_plan_from_default(self, default_plan_dict: dict[str, Any] | None = None) -> ReviewPlanModel:
        payload = default_plan_dict or DEFAULT_REVIEW_SITE
        plan_info = payload.get("plan") or {}
        phases = list(payload.get("phases") or [])
        days = list(payload.get("days") or [])
        tasks_per_day: dict[str, list[dict[str, Any]]] = {}
        for day in days:
            day_key = str(day.get("id") or "")
            tasks_per_day[day_key] = list(day.get("tasks") or [])
        intro_scripts = list(payload.get("intro_scripts") or [])
        star_cards = list(payload.get("star_cards") or [])
        a4_memory = list(payload.get("a4_memory") or [])
        return await self.create_plan(
            plan_data=plan_info,
            phases=phases,
            days=days,
            tasks_per_day=tasks_per_day,
            intro_scripts=intro_scripts,
            star_cards=star_cards,
            a4_memory=a4_memory,
        )


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None
