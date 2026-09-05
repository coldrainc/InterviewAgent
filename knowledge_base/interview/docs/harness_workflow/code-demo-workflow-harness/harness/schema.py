"""Harness 数据模型（Scenario / Trajectory / Span）。

设计原则：
- Pydantic v2，方便 JSON 序列化/校验；
- Trajectory schema 与 OTel 语义对齐（trace_id / span_id / parent_span_id / status）；
- Scenario 声明式 yaml，非工程师也能写用例。
"""

from __future__ import annotations

import time
import uuid
import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Scenario Registry
# ---------------------------------------------------------------------------

class AssertionType(str, Enum):
    TOOL_CALLED = "tool_called"
    MAX_STEPS = "max_steps"
    ANSWER_CONTAINS = "answer_contains"
    LLM_JUDGE = "llm_judge"
    COST_BELOW = "cost_below"
    NO_FORBIDDEN_TOOL = "no_forbidden_tool"


class Assertion(BaseModel):
    type: AssertionType
    # tool_called
    tool_name: Optional[str] = None
    args_match: Optional[dict[str, Any]] = None
    # max_steps / cost_below
    value: Optional[float] = None
    # answer_contains
    answers: Optional[list[str]] = None
    # llm_judge
    criteria: Optional[str] = None
    model: Optional[str] = "gpt-4o-mini"
    # no_forbidden_tool
    forbidden_tools: Optional[list[str]] = None


class ScenarioInput(BaseModel):
    user_prompt: str
    context: dict[str, Any] = Field(default_factory=dict)


class GoldenHints(BaseModel):
    must_include_tool_sequence: list[str] = Field(default_factory=list)
    should_contain_in_final_answer: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    version: str
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    difficulty: str = "medium"
    input: ScenarioInput
    assertions: list[Assertion]
    golden_trajectory_hints: GoldenHints = Field(default_factory=GoldenHints)
    tools_whitelist: list[str] = Field(default_factory=list)
    seed: int = 42

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def build_execution_context(self, seed: Optional[int] = None) -> dict[str, Any]:
        """把 scenario 组装成 agent 执行时的初始 context。"""
        ctx = dict(self.input.context)
        ctx.setdefault("_scenario_id", self.id)
        ctx.setdefault("_scenario_seed", seed or self.seed)
        return ctx


# ---------------------------------------------------------------------------
# Trajectory + Span（OTel 兼容语义）
# ---------------------------------------------------------------------------

class SpanType(str, Enum):
    LLM_REASONING = "llm_reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SANDBOX_STATE = "sandbox_state_change"
    USER_TURN = "user_turn"
    FINAL_ANSWER = "final_answer"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    TRUNCATED = "truncated"
    SKIPPED = "skipped"


class Span(BaseModel):
    span_id: str = Field(default_factory=lambda: f"sp_{uuid.uuid4().hex[:6]}")
    parent_span_id: Optional[str] = None
    type: SpanType
    name: str
    started_at: float = Field(default_factory=time.time)
    duration_ms: float = 0.0
    token_count: int = 0
    cost_usd: float = 0.0
    status: SpanStatus = SpanStatus.OK
    # 字段按需使用；对不同 type 只需填必要的
    input: dict[str, Any] = Field(default_factory=dict)
    output_snippet: str = ""          # 结果摘要，原文存外部存储
    # tool_call 专用
    tool_name: Optional[str] = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    # 错误信息
    error_message: Optional[str] = None

    @classmethod
    def from_turn(cls, turn: dict[str, Any], parent: Optional["Span"] = None) -> "Span":
        """从 agent 输出的 turn 构造 span。
        turn schema: {"type":..., "name":..., "duration_ms":..., ...}
        """
        t = turn.get("type", "llm_reasoning")
        return cls(
            parent_span_id=parent.span_id if parent else None,
            type=SpanType(t),
            name=turn.get("name", t),
            duration_ms=float(turn.get("duration_ms", 0)),
            token_count=int(turn.get("token_count", 0)),
            cost_usd=float(turn.get("cost_usd", 0)),
            status=SpanStatus(turn.get("status", "ok")),
            input=turn.get("input", {}),
            output_snippet=turn.get("output_snippet", "") or "",
            tool_name=turn.get("tool_name"),
            tool_args=turn.get("tool_args", {}),
            error_message=turn.get("error"),
        )


class EvidenceRef(BaseModel):
    doc_id: str
    chunk_index: int = 0
    relevance_score: float = 0.0


class Trajectory(BaseModel):
    trace_id: str
    agent_run_id: str = Field(default_factory=lambda: f"ar_{uuid.uuid4().hex[:6]}")
    started_at: float
    ended_at: float
    total_token_count: int
    total_cost_usd: float
    spans: list[Span] = Field(default_factory=list)
    evidence_bank_refs: list[EvidenceRef] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    def dump_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                              encoding="utf-8")
