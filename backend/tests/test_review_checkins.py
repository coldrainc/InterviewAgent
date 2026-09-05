"""Task 4 日历打卡 / streak / 时长聚合测试。

覆盖：
- TR-4.1 跨天 checkin 的 current_streak/longest_streak，断签归零；
- TR-4.2 today 接口按 scheduled_date 返回当天任务与完成态；
- TR-4.3 重复 checkin 幂等（单行、计数稳定）；
- 计划激活写 start_date 与天 scheduled_date；进度变更自动聚合当日打卡；
- API 端到端：激活 -> today -> checkin -> checkins。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import (
    Base,
    ReviewCheckinModel,
    ReviewDayModel,
    ReviewPlanModel,
    ReviewTaskModel,
)
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app
from interview_agent.repositories.review_checkin_repository import ReviewCheckinRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.review_checkin_service import ReviewCheckinService

TENANT = "default"
USER = "anonymous"


@pytest_asyncio.fixture
async def db_factory():
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_plan(factory, *, days: int = 2, tasks_per_day: int = 2, status: str = "draft") -> uuid.UUID:
    async with factory() as db:
        plan = ReviewPlanModel(
            tenant_id=TENANT,
            user_id=USER,
            plan_key=f"plan-{uuid.uuid4().hex[:8]}",
            title="打卡测试计划",
            status=status,
        )
        db.add(plan)
        await db.flush()
        for day_index in range(days):
            day = ReviewDayModel(
                plan_id=plan.id,
                tenant_id=TENANT,
                user_id=USER,
                day_key=f"day-{day_index + 1:02d}",
                day_label=f"第{day_index + 1}天",
                sort_order=day_index + 1,
            )
            db.add(day)
            await db.flush()
            for task_index in range(tasks_per_day):
                db.add(
                    ReviewTaskModel(
                        plan_id=plan.id,
                        day_id=day.id,
                        tenant_id=TENANT,
                        user_id=USER,
                        task_key=f"t-{day_index + 1}-{task_index + 1}",
                        title=f"任务{day_index + 1}-{task_index + 1}",
                        sort_order=task_index + 1,
                    )
                )
        await db.commit()
        return plan.id


# ---- 计划激活排期 ----
@pytest.mark.asyncio
async def test_activate_plan_sets_start_date_and_schedules_days(db_factory) -> None:
    plan_id = await _seed_plan(db_factory, days=3)
    async with db_factory() as db:
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        updated = await repo.update_plan(plan_id, {"status": "active", "start_date": "2026-09-07"})
        assert updated is not None
        assert updated.start_date == date(2026, 9, 7)
        days = await repo.list_days(plan_id, with_tasks=False)
        scheduled = sorted((day.scheduled_date for day in days))
        assert scheduled == [date(2026, 9, 7), date(2026, 9, 8), date(2026, 9, 9)]


# ---- TR-4.2 today 返回当天任务 ----
@pytest.mark.asyncio
async def test_get_today_returns_scheduled_day_and_progress(db_factory) -> None:
    today = date(2026, 9, 8)
    plan_id = await _seed_plan(db_factory, days=2, tasks_per_day=2)
    async with db_factory() as db:
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        await repo.update_plan(plan_id, {"status": "active", "start_date": "2026-09-07"})
        days = await repo.list_days(plan_id)
        today_day = next(day for day in days if day.scheduled_date == today)
        first_task = sorted(today_day.tasks, key=lambda t: t.sort_order)[0]
        await repo.update_progress(first_task.id, {"done": True, "elapsed_minutes": 25})

        service = ReviewCheckinService(db, tenant_id=TENANT, user_id=USER)
        result = await service.get_today(plan_id, today=today)

        assert result["active"] is True
        assert result["date"] == today.isoformat()
        assert result["day"]["scheduled_date"] == today.isoformat()
        assert len(result["tasks"]) == 2
        assert result["summary"]["tasks_done"] == 1
        assert result["summary"]["total_tasks"] == 2
        assert result["summary"]["elapsed_minutes"] == 25


@pytest.mark.asyncio
async def test_get_today_empty_when_plan_not_active(db_factory) -> None:
    plan_id = await _seed_plan(db_factory)
    async with db_factory() as db:
        service = ReviewCheckinService(db, tenant_id=TENANT, user_id=USER)
        result = await service.get_today(plan_id, today=date.today())
        assert result["active"] is False
        assert result["day"] is None
        assert result["tasks"] == []


# ---- TR-4.3 重复打卡幂等 ----
@pytest.mark.asyncio
async def test_checkin_is_idempotent(db_factory) -> None:
    today = date(2026, 9, 7)
    plan_id = await _seed_plan(db_factory, days=1, tasks_per_day=2)
    async with db_factory() as db:
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        await repo.update_plan(plan_id, {"status": "active", "start_date": "2026-09-07"})
        days = await repo.list_days(plan_id)
        task = sorted(days[0].tasks, key=lambda t: t.sort_order)[0]
        await repo.update_progress(task.id, {"done": True})

        service = ReviewCheckinService(db, tenant_id=TENANT, user_id=USER)
        first = await service.checkin(plan_id, elapsed_minutes=30, note="开始打卡", today=today)
        assert first["checkin"]["tasks_done"] == 1
        assert first["checkin"]["total_tasks"] == 2
        assert first["checkin"]["elapsed_minutes"] == 30

        # 重复打卡不带时长：计数/时长稳定，仍单行
        second = await service.checkin(plan_id, note="继续复习", today=today)
        assert second["checkin"]["tasks_done"] == 1
        assert second["checkin"]["elapsed_minutes"] == 30
        assert second["checkin"]["note"] == "继续复习"

        # 追加学习时长累加，记录仍只有一条
        third = await service.checkin(plan_id, elapsed_minutes=15, today=today)
        assert third["checkin"]["elapsed_minutes"] == 45

        rows = (await db.execute(select(ReviewCheckinModel))).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_checkin_requires_active_plan(db_factory) -> None:
    plan_id = await _seed_plan(db_factory)
    async with db_factory() as db:
        service = ReviewCheckinService(db, tenant_id=TENANT, user_id=USER)
        with pytest.raises(ValueError):
            await service.checkin(plan_id, today=date.today())


# ---- TR-4.1 streak ----
@pytest.mark.asyncio
async def test_streak_current_and_longest(db_factory) -> None:
    plan_id = await _seed_plan(db_factory, days=1)
    today = date(2026, 9, 8)
    async with db_factory() as db:
        repo = ReviewCheckinRepository(db, tenant_id=TENANT, user_id=USER)
        for offset in (5, 4, 3, 1, 0):  # 3 连段 + 2 连段（今天/昨天）
            await repo.upsert_checkin(
                plan_id,
                today - timedelta(days=offset),
                tasks_done=1,
                total_tasks=2,
                elapsed_minutes=20,
            )
        streak = await repo.compute_streak(plan_id=plan_id, today=today)
        assert streak["current_streak"] == 2
        assert streak["longest_streak"] == 3
        assert streak["total_checkin_days"] == 5
        assert streak["last_checkin_date"] == today.isoformat()


@pytest.mark.asyncio
async def test_streak_resets_after_break(db_factory) -> None:
    plan_id = await _seed_plan(db_factory, days=1)
    today = date(2026, 9, 8)
    async with db_factory() as db:
        repo = ReviewCheckinRepository(db, tenant_id=TENANT, user_id=USER)
        for offset in (5, 4, 3):  # 最近打卡在 3 天前 -> 断签
            await repo.upsert_checkin(
                plan_id,
                today - timedelta(days=offset),
                tasks_done=1,
                total_tasks=2,
                elapsed_minutes=20,
            )
        streak = await repo.compute_streak(plan_id=plan_id, today=today)
        assert streak["current_streak"] == 0
        assert streak["longest_streak"] == 3


# ---- 进度变更自动同步当日打卡 ----
@pytest.mark.asyncio
async def test_progress_update_syncs_today_checkin(db_factory) -> None:
    today = date(2026, 9, 7)
    plan_id = await _seed_plan(db_factory, days=1, tasks_per_day=2)
    async with db_factory() as db:
        repo = ReviewSiteRepository(db, tenant_id=TENANT, user_id=USER)
        await repo.update_plan(plan_id, {"status": "active", "start_date": "2026-09-07"})
        days = await repo.list_days(plan_id)
        task = sorted(days[0].tasks, key=lambda t: t.sort_order)[0]
        await repo.update_progress(task.id, {"done": True, "elapsed_minutes": 40})

        service = ReviewCheckinService(db, tenant_id=TENANT, user_id=USER)
        synced = await service.sync_day_checkin(plan_id, days[0].id, today=today)
        assert synced is not None
        assert synced["tasks_done"] == 1
        assert synced["total_tasks"] == 2
        assert synced["elapsed_minutes"] == 40


# ---- API 端到端 ----
def _register_headers(client: TestClient, email: str) -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": f"198.51.100.{ip_suffix}"},
        json={"email": email, "password": "passw0rd!", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_checkin_flow_end_to_end(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="checkin-api")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "checkin-e2e@example.com")

        imported = client.post("/review-site/import", headers=headers, json={"plan_only": True})
        assert imported.status_code == 200
        plan_id = client.get("/review-site/plans", headers=headers).json()[0]["id"]

        activated = client.patch(f"/review-site/plans/{plan_id}", headers=headers, json={"status": "active"})
        assert activated.status_code == 200
        assert activated.json()["status"] == "active"

        today_resp = client.get(f"/review-site/plans/{plan_id}/today", headers=headers)
        assert today_resp.status_code == 200
        today_body = today_resp.json()
        assert today_body["active"] is True
        assert today_body["day"] is not None
        assert len(today_body["tasks"]) >= 1

        checkin = client.post(
            f"/review-site/plans/{plan_id}/checkin",
            headers=headers,
            json={"elapsed_minutes": 35, "note": "完成第一天任务"},
        )
        assert checkin.status_code == 200, checkin.text
        assert checkin.json()["streak"]["current_streak"] == 1

        # 重复打卡幂等
        client.post(f"/review-site/plans/{plan_id}/checkin", headers=headers, json={"note": "晚间复习"})
        listing = client.get("/review-site/checkins", headers=headers)
        assert listing.status_code == 200
        body = listing.json()
        assert len(body["checkins"]) == 1
        assert body["streak"]["current_streak"] == 1
        assert body["checkins"][0]["note"] == "晚间复习"

    import asyncio

    asyncio.run(engine.dispose())
