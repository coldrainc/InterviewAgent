"""Celery worker：把 Run 和 Analyzer 两个任务放异步队列，避免 API 被长任务占住。
生产建议 4 并发起步，再随压力 KEDA 弹性扩。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import structlog
from celery import Celery

from ..config import get_settings

log = structlog.get_logger()
s = get_settings()

celery_app = Celery(
    "harness_workers",
    broker=s.CELERY_BROKER,
    backend=s.CELERY_BACKEND,
    include=["app.tasks.runner_worker", "app.tasks.analyzer_worker"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_time_limit=s.RUN_MAX_TIMEOUT_SEC + 60,
    task_acks_late=True,          # worker 崩溃不丢任务
    worker_prefetch_multiplier=1, # 防止某 worker 被大任务堆死
)


def _run_sync(coro):
    """Celery 同步函数里调 async DB/Service 的桥接。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="runner.run_scenario", queue="run_queue",
                 autoretry_for=(Exception,), retry_backoff=3, retry_jitter=True,
                 max_retries=s.RUN_MAX_RETRIES,
                 rate_limit="60/m")  # 限流防 LLM 429
def run_scenario_task(scenario_id: str, gate_level: str, triggered_by: str,
                      commit_sha: str | None = None, pr_id: str | None = None):
    from ..services.run_manager import RunManager
    rm = RunManager()
    run = _run_sync(rm.run_scenario(
        scenario_id=scenario_id, gate_level=gate_level,
        triggered_by=triggered_by, commit_sha=commit_sha, pr_id=pr_id,
    ))
    # 完成后触发 analyzer（可以异步或同步，这里延迟触发）
    from .analyzer_worker import analyze_run_task
    analyze_run_task.apply_async((str(run.id),), queue="analyzer_queue",
                                 countdown=3)
    return {"run_id": str(run.id), "gate_passed": run.gate_passed}


@celery_app.task(name="runner.kill_stale_runs", queue="run_queue")
def kill_stale_runs():
    """定时：把超过阈值仍为 running 的 run 标记为 timeout，避免僵尸 run。"""
    from ..repos.repos import RunRepo
    from ..models.mongo import RunDoc
    async def _inner():
        timeout_sec = get_settings().RUN_MAX_TIMEOUT_SEC
        stuck = await RunRepo.find_stuck(timeout_sec)
        for r in stuck:
            log.warn("stale_run_killed", run_id=str(r.id),
                     scenario=r.scenario_id, started_at=str(r.started_at))
            await RunRepo.set_status(r.id, "timeout", runtime_error="hard_timeout_killed",
                                     gate_passed=False,
                                     gate_reasons=[f"RUN TIMEOUT 超过 {timeout_sec}s 被 kill"])
    _run_sync(_inner())
    return f"killed_stale"
