"""Scenarios / Runs / Baselines 的 Mongo 仓储层。所有 DB 读写集中于此，便于替换存储或做 mock。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from beanie import PydanticObjectId
from structlog import get_logger

from ..models.mongo import (
    AnalyzerFindingDoc, BaselineDoc, RunDoc, ScenarioDoc, SpanDoc,
)

log = get_logger()


class ScenarioRepo:
    @staticmethod
    async def get(scenario_id: str, version: Optional[str] = None) -> Optional[ScenarioDoc]:
        q: dict[str, Any] = {"scenario_id": scenario_id, "status": "active"}
        if version:
            q["version"] = version
        return await ScenarioDoc.find_one(q, sort=[("updated_at", -1)])

    @staticmethod
    async def list(*, page: int = 1, page_size: int = 50,
                   tags: Optional[list[str]] = None,
                   keyword: Optional[str] = None) -> tuple[list[ScenarioDoc], int]:
        query: dict[str, Any] = {"status": "active"}
        if tags:
            query["tags"] = {"$all": tags}
        if keyword:
            query["$or"] = [
                {"scenario_id": {"$regex": keyword, "$options": "i"}},
                {"input.user_prompt": {"$regex": keyword, "$options": "i"}},
            ]
        total = await ScenarioDoc.find(query).count()
        items = await ScenarioDoc.find(query).sort("-updated_at").skip(
            max(0, page - 1) * page_size).limit(page_size).to_list()
        return items, total

    @staticmethod
    async def upsert(doc: ScenarioDoc) -> ScenarioDoc:
        doc.updated_at = datetime.utcnow()
        return await doc.save()


class RunRepo:
    @staticmethod
    async def create(doc: RunDoc) -> RunDoc:
        return await doc.insert()

    @staticmethod
    async def get(run_id: PydanticObjectId) -> Optional[RunDoc]:
        return await RunDoc.get(run_id)

    @staticmethod
    async def set_status(run_id: PydanticObjectId, status: str, **extra) -> None:
        upd: dict[str, Any] = {"status": status, "ended_at": datetime.utcnow()}
        upd.update(extra)
        await RunDoc.find_one(RunDoc.id == run_id).update({"$set": upd})

    @staticmethod
    async def append_spans(run_id: PydanticObjectId, spans: list[SpanDoc]) -> None:
        if spans:
            for s in spans:
                s.run_id = run_id
            await SpanDoc.insert_many(spans)

    @staticmethod
    async def add_findings(run_id: PydanticObjectId, findings: list[AnalyzerFindingDoc]) -> None:
        for f in findings:
            f.run_id = run_id
        if findings:
            await AnalyzerFindingDoc.insert_many(findings)

    @staticmethod
    async def aggregate(start: datetime, end: datetime, group_by: str = "gate_level") -> list[dict]:
        """指标聚合（核心监控用）。"""
        pipeline = [
            {"$match": {"started_at": {"$gte": start, "$lte": end},
                        "status": {"$in": ["succeeded", "failed"]}}},
            {"$group": {
                "_id": f"${group_by}",
                "count": {"$sum": 1},
                "pass_rate": {"$avg": {"$cond": ["$gate_passed", 1, 0]}},
                "task_success_rate_avg": {"$avg": "$metrics.task_success_rate"},
                "tool_acc_avg": {"$avg": "$metrics.tool_selection_acc"},
                "3d_avg": {"$avg": "$metrics.3d_overall"},
                "cost_usd_sum": {"$sum": "$metrics.total_cost_usd"},
                "latency_p95_ms": {
                    "$percentile": {"input": "$duration_ms", "p": [0.95], "method": "approximate"}
                },
            }},
        ]
        return await RunDoc.aggregate(pipeline).to_list(length=100)

    @staticmethod
    async def find_stuck(timeout_sec: int) -> list[RunDoc]:
        """找出 running 超过阈值的 run（用于重跑 / 超时 kill）。"""
        limit = datetime.utcnow() - timedelta(seconds=timeout_sec)
        return await RunDoc.find(
            {"status": "running", "started_at": {"$lte": limit}}
        ).to_list(length=500)


class BaselineRepo:
    @staticmethod
    async def latest(baseline_id: str = "default") -> Optional[BaselineDoc]:
        return await BaselineDoc.find_one(
            {"baseline_id": baseline_id}, sort=[("created_at", -1)])

    @staticmethod
    async def create(doc: BaselineDoc) -> BaselineDoc:
        return await doc.insert()

    @staticmethod
    async def history(baseline_id: str = "default", limit: int = 20) -> list[BaselineDoc]:
        return await BaselineDoc.find({"baseline_id": baseline_id}
                                      ).sort("-created_at").limit(limit).to_list()
