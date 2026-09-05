"""FastAPI app：启动 Beanie/Mongo、注册路由、加载 OTel + Prometheus、健康检查、止血开关。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import structlog
from beanie import init_beanie
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import Settings, get_settings
from .models.mongo import (
    AnalyzerFindingDoc, AuditLogDoc, BaselineDoc, RunDoc, ScenarioDoc, SpanDoc,
)
from .repos.repos import BaselineRepo, RunRepo, ScenarioRepo
from .schema import Scenario, ScenarioInput  # 复用 demo 中的 Scenario schema
from .security import User, audit_logging, current_user, require
from .services.gate_logic import decide
from .services.run_manager import RunManager
from .telemetry.observability import (
    API_LATENCY, API_REQUESTS, QUEUE_LAG, RUNS_TOTAL, SCENARIO_COUNT, setup_otel,
)

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Lifespan：Beanie + Celery + 计数预热
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings
    log.info("startup", env=s.ENV, mongo_uri=s.MONGO_URI.get_secret_value()[:16] + "...")

    # MongoDB + Beanie
    mongo_client = AsyncIOMotorClient(s.MONGO_URI.get_secret_value(),
                                      minPoolSize=s.MONGO_MIN_POOL,
                                      maxPoolSize=s.MONGO_MAX_POOL)
    await init_beanie(
        database=getattr(mongo_client, s.MONGO_DB_NAME),
        document_models=[ScenarioDoc, RunDoc, SpanDoc, BaselineDoc,
                         AnalyzerFindingDoc, AuditLogDoc],
    )
    app.state.mongo = mongo_client
    app.state.run_manager = RunManager(settings=s)

    # OTel + instruments
    setup_otel(app)

    # 预热 Gauge
    await refresh_gauges()

    log.info("startup.done")
    yield
    mongo_client.close()
    log.info("shutdown.done")


async def refresh_gauges() -> None:
    """定期调用刷新 Gauge。"""
    total_active = await ScenarioDoc.find({"status": "active"}).count()
    total_frozen = await ScenarioDoc.find({"status": "frozen"}).count()
    SCENARIO_COUNT.labels(status="active").set(total_active)
    SCENARIO_COUNT.labels(status="frozen").set(total_frozen)


# ---------------------------------------------------------------------------
# App 实例
# ---------------------------------------------------------------------------

def create_app(settings: Optional[Settings] = None) -> FastAPI:
    s = settings or get_settings()
    app = FastAPI(
        title="Workflow Agent Harness API",
        version="0.1.0",
        description="Scenario Registry · Run Executor · Gate · Report",
        lifespan=lifespan,
    )
    app.state.settings = s

    # CORS
    app.add_middleware(CORSMiddleware,
                       allow_origins=["*"] if s.ENV in ("dev", "test") else [
                           # 生产填公司内部域名
                       ], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    # Prometheus metrics middleware（简易）
    @app.middleware("http")
    async def _metrics_mw(request: Request, call_next):
        import time
        t0 = time.perf_counter()
        resp: Response = await call_next(request)
        elapsed = time.perf_counter() - t0
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        API_LATENCY.labels(request.method, path, resp.status_code).observe(elapsed)
        API_REQUESTS.labels(request.method, path, resp.status_code).inc()
        RUNS_TOTAL  # 保持引用（实际由 worker 内 inc）
        QUEUE_LAG   # 保持引用
        return resp

    app.middleware("http")(audit_logging)

    register_routes(app)
    return app


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

def register_routes(app: FastAPI) -> None:
    s: Settings = app.state.settings

    # --- 健康 ---
    @app.get("/healthz", tags=["ops"])
    async def healthz():
        # Mongo 连通性探测
        try:
            await app.state.mongo.admin.command("ping")
        except Exception as e:
            raise HTTPException(503, f"mongo_ping_failed: {e!r}")
        return {"ok": True, "env": s.ENV, "gate_enabled": s.GATE_ENABLED}

    @app.get("/metrics", tags=["ops"])
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # --- 止血开关（仅 admin）---
    @app.post("/ops/gate-toggle", tags=["ops"],
              dependencies=[Depends(require("admin", "update"))])
    async def gate_toggle(enabled: bool, deferred_llm_pass: bool = False,
                          user: User = Depends(current_user)):
        # 仅运行时生效（重启会回到 env 值；要永久生效要改 env/config）
        s.GATE_ENABLED = enabled
        s.DEFERRED_LLM_AS_PASS = deferred_llm_pass
        log.warn("gate_config_changed", by=user.sub, enabled=enabled,
                 deferred_llm_pass=deferred_llm_pass)
        return {"gate_enabled": s.GATE_ENABLED,
                "deferred_llm_as_pass": s.DEFERRED_LLM_AS_PASS}

    # --- Scenario CRUD ---
    @app.get("/scenarios", tags=["scenarios"],
             dependencies=[Depends(require("scenarios", "read"))])
    async def list_scenarios(
        page: int = 1, page_size: int = Query(50, ge=1, le=200),
        tags: Optional[list[str]] = Query(default=None),
        keyword: Optional[str] = None,
    ):
        items, total = await ScenarioRepo.list(page=page, page_size=page_size,
                                                tags=tags, keyword=keyword)
        return {"items": [i.model_dump() for i in items], "total": total,
                "page": page, "page_size": page_size}

    @app.get("/scenarios/{scenario_id}", tags=["scenarios"])
    async def get_scenario(scenario_id: str, version: Optional[str] = None,
                          _: User = Depends(require("scenarios", "read"))):
        doc = await ScenarioRepo.get(scenario_id, version)
        if not doc:
            raise HTTPException(404, "not found")
        return doc.model_dump()

    @app.post("/scenarios", tags=["scenarios"], status_code=201,
              dependencies=[Depends(require("scenarios", "write"))])
    async def create_scenario(payload: Scenario,
                              user: User = Depends(current_user)):
        # 映射 payload 到 ScenarioDoc（schema 与 Mongo 模型字段大部分重合）
        doc = ScenarioDoc(**payload.model_dump(exclude_none=True))
        doc.created_by = doc.updated_by = user.sub
        await ScenarioRepo.upsert(doc)
        await refresh_gauges()
        return doc.model_dump()

    @app.put("/scenarios/{scenario_id}", tags=["scenarios"],
              dependencies=[Depends(require("scenarios", "write"))])
    async def update_scenario(scenario_id: str, payload: Scenario,
                              user: User = Depends(current_user)):
        doc = await ScenarioRepo.get(scenario_id)
        if not doc:
            raise HTTPException(404)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(doc, k, v)
        doc.updated_by = user.sub
        await ScenarioRepo.upsert(doc)
        return doc.model_dump()

    # --- Runs ---
    @app.post("/runs/trigger", tags=["runs"], status_code=202,
              dependencies=[Depends(require("runs", "trigger"))])
    async def trigger_run(scenario_id: str, gate_level: str = "test",
                          commit_sha: Optional[str] = None,
                          pr_id: Optional[str] = None,
                          dry_run: bool = False,
                          user: User = Depends(current_user)):
        """同步触发一次 run，用于 dry-run 或小量验证。
        生产大批量应走 Celery Worker（见 tasks/runner_worker.py）。"""
        rm: RunManager = app.state.run_manager
        run = await rm.run_scenario(scenario_id=scenario_id, gate_level=gate_level,
                                    triggered_by=user.sub, commit_sha=commit_sha,
                                    pr_id=pr_id, dry_run=dry_run)
        return {"run_id": str(run.id), "gate_passed": run.gate_passed,
                "gate_reasons": run.gate_reasons,
                "metrics": run.metrics}

    @app.post("/runs/batch", tags=["runs"], status_code=202,
              dependencies=[Depends(require("runs", "trigger"))])
    async def batch_trigger(scenario_ids: list[str], gate_level: str = "test",
                            commit_sha: Optional[str] = None,
                            pr_id: Optional[str] = None,
                            user: User = Depends(current_user)):
        """批量：把任务交给 Celery，立即返回一组 task_id。"""
        from .tasks.runner_worker import run_scenario_task
        ids: list[str] = []
        for sid in scenario_ids:
            task = run_scenario_task.delay(sid, gate_level, user.sub, commit_sha, pr_id)
            ids.append(task.id)
        return {"task_ids": ids}

    @app.get("/runs/{run_id}", tags=["runs"])
    async def get_run(run_id: str, _: User = Depends(require("runs", "read"))):
        from beanie import PydanticObjectId
        run = await RunRepo.get(PydanticObjectId(run_id))
        if not run:
            raise HTTPException(404)
        return run.model_dump()

    @app.get("/reports/summary", tags=["reports"])
    async def report_summary(last_hours: int = Query(24, ge=1, le=24*30),
                             _: User = Depends(current_user)):
        """给 Grafana/看板：近 X 小时聚合指标。"""
        end = datetime.utcnow()
        start = end - timedelta(hours=last_hours)
        agg = await RunRepo.aggregate(start, end, group_by="gate_level")
        return {"window_hours": last_hours, "by_gate_level": agg}

    # --- Baselines ---
    @app.get("/baselines/latest", tags=["baselines"],
             dependencies=[Depends(require("baselines", "read"))])
    async def get_latest_baseline(baseline_id: str = "default"):
        doc = await BaselineRepo.latest(baseline_id)
        if not doc:
            raise HTTPException(404)
        return doc.model_dump()

    @app.post("/baselines", tags=["baselines"], status_code=201,
              dependencies=[Depends(require("baselines", "update"))])
    async def create_baseline(baseline_id: str, metrics: dict[str, float],
                              scenario_count: int, note: Optional[str] = None,
                              version: str = "1.0",
                              user: User = Depends(current_user)):
        from .models.mongo import BaselineDoc as BD
        doc = BD(baseline_id=baseline_id, version=version, metrics=metrics,
                 scenario_count=scenario_count, created_by=user.sub, note=note)
        await BaselineRepo.create(doc)
        return doc.model_dump()

    @app.post("/baselines/decide-preview", tags=["baselines"])
    async def decide_preview(new_metrics: dict[str, float],
                            baseline_id: str = "default",
                            gate_level: str = "agent"):
        """提前看"如果把这些指标当本次结果，门禁会怎样决策"。"""
        latest = await BaselineRepo.latest(baseline_id)
        base = latest.metrics if latest else {}
        d = decide(new_metrics, base, gate_level)
        return {"baseline": base, "new": new_metrics,
                "passed": d.passed, "reasons": d.reasons}


app = create_app()
