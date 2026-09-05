"""Mongo 文档模型（Beanie ODM — Pydantic + Motor）。
选用 Beanie 而不是纯 Motor，原因：ODM + 索引/Migration 管理更清晰、Pydantic 直连，适合生产演进。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from beanie import Document, PydanticObjectId
from pydantic import Field

from ..schema import Assertion, GoldenHints, ScenarioInput


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

class ScenarioDoc(Document):
    """Scenario 持久化文档 + 版本历史。"""
    scenario_id: str = Field(index=True)
    version: str
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    difficulty: str = "medium"
    input: ScenarioInput
    assertions: list[Assertion]
    golden_trajectory_hints: GoldenHints = Field(default_factory=GoldenHints)
    tools_whitelist: list[str] = Field(default_factory=list)
    seed: int = 42

    status: str = Field(default="active", pattern="^(active|frozen|archived)$")
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "scenarios"
        indexes = [
            [("scenario_id", 1), ("version", -1)],
            [("tags", 1)],
            [("status", 1)],
            "created_at",
        ]
        use_state_management = True


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class SpanDoc(Document):
    """Span 单集合（量大会按天分集合，见 Beanie UnionDoc / Views）。初期一张表够用。"""
    run_id: PydanticObjectId = Field(index=True)
    span_id: str
    parent_span_id: Optional[str] = None
    type: str
    name: str
    started_at: datetime
    duration_ms: float = 0.0
    token_count: int = 0
    cost_usd: float = 0.0
    status: str
    tool_name: Optional[str] = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    input_snippet: str = ""
    output_snippet: str = ""
    error_message: Optional[str] = None

    class Settings:
        name = "spans"
        indexes = [
            [("run_id", 1), ("type", 1)],
            [("tool_name", 1), ("started_at", -1)],
            [("status", 1), ("started_at", -1)],
        ]


class RunDoc(Document):
    """一次 scenario 执行的完整记录。"""
    trace_id: str = Field(index=True)
    agent_run_id: str
    scenario_id: str = Field(index=True)
    scenario_version: str
    gate_level: str = Field(default="test")
    triggered_by: str = "system"                 # 用户名 / ci-service-account
    commit_sha: Optional[str] = None
    pr_id: Optional[str] = None

    status: str = Field(default="pending",
                        pattern="^(pending|running|succeeded|failed|timeout|canceled)$")
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # 运行时错误（非业务断言失败，而是 agent 崩溃、环境不可用）
    runtime_error: Optional[str] = None

    metrics: dict[str, Any] = Field(default_factory=dict)   # evaluators.metrics 结果
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    analyzer_findings_summary: dict[str, Any] = Field(default_factory=dict)
    llm_judge_results: list[dict[str, Any]] = Field(default_factory=list)

    # 门禁决策
    gate_passed: Optional[bool] = None
    gate_reasons: list[str] = Field(default_factory=list)

    class Settings:
        name = "runs"
        indexes = [
            [("scenario_id", 1), ("started_at", -1)],
            [("gate_level", 1), ("status", 1), ("started_at", -1)],
            [("gate_passed", 1), ("started_at", -1)],
            "triggered_by",
            [("commit_sha", 1)],
        ]


# ---------------------------------------------------------------------------
# Baseline（版本化）
# ---------------------------------------------------------------------------

class BaselineDoc(Document):
    baseline_id: str = Field(default="default")
    version: str
    metrics: dict[str, float] = Field(default_factory=dict)
    scenario_count: int = 0
    created_by: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    class Settings:
        name = "baselines"
        indexes = [[("baseline_id", 1), ("created_at", -1)]]


# ---------------------------------------------------------------------------
# Analyzer Findings（诊断结果）
# ---------------------------------------------------------------------------

class AnalyzerFindingDoc(Document):
    run_id: PydanticObjectId = Field(index=True)
    tag: str = Field(index=True)
    severity: str
    span_indices: list[int] = Field(default_factory=list)
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "analyzer_findings"
        indexes = [[("tag", 1), ("severity", 1), ("created_at", -1)]]


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------

class AuditLogDoc(Document):
    """所有写操作：谁、什么动作、什么对象、时间、IP。"""
    user: str = "anonymous"
    action: str                        # create/update/delete/run_trigger/gate_toggle/...
    resource: str                      # scenario/run/baseline/...
    resource_id: Optional[str] = None
    ip: Optional[str] = None
    diff: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    class Settings:
        name = "audit_logs"
        indexes = [
            [("user", 1), ("created_at", -1)],
            [("action", 1), ("resource", 1), ("created_at", -1)],
        ]
