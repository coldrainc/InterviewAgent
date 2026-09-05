"""ScenarioRunner：跑 scenario、采集 trajectory。

与 Agent 执行层解耦——通过 `AgentExecutor` protocol 接入，自研 Runtime / LangGraph 都可以。
"""

from __future__ import annotations

import time
from typing import Any, Iterator, Protocol, Optional

from .schema import Scenario, Trajectory, Span, SpanType, EvidenceRef


class AgentExecutor(Protocol):
    """你现有 Workflow Agent 执行引擎实现这个协议即可接入 harness。"""

    def run_stream(
        self,
        user_prompt: str,
        context: dict[str, Any],
        tools_whitelist: list[str],
        seed: int,
    ) -> Iterator[dict[str, Any]]:
        """流式返回 turn。turn schema（示例）：

        {"type": "llm_reasoning", "name": "step1_reason",
         "duration_ms": 120, "token_count": 420, "cost_usd": 0.002,
         "status": "ok", "input": {...}, "output_snippet": "打算调用 xxx", ...}
        {"type": "tool_call", "name": "get_trace_detail",
         "tool_name": "get_trace_detail", "tool_args": {"trace_id": "tr_123"}, ...}
        {"type": "final_answer", "output_snippet": "根因是... 建议...",
         "evidence_refs": [{"doc_id": "...", ...}], ...}
        """
        ...


class DummyAgent(AgentExecutor):
    """用于开发/演示的假 agent，按 golden hints 顺序吐假 span。"""

    def run_stream(self, user_prompt, context, tools_whitelist, seed):
        for i, tool in enumerate(context.get("_golden_tools", ["get_trace_detail",
                                                              "sandbox_check_config_integrity"])):
            yield {
                "type": "llm_reasoning", "name": f"react_{i}",
                "duration_ms": 150 + i * 30, "token_count": 300, "cost_usd": 0.001,
                "status": "ok", "output_snippet": f"决定调用 {tool}",
            }
            yield {
                "type": "tool_call", "name": tool,
                "tool_name": tool, "tool_args": {"trace_id": "tr_abc123"},
                "duration_ms": 60, "status": "ok", "output_snippet": "config hash mismatch",
            }
        yield {
            "type": "final_answer", "name": "final",
            "duration_ms": 100, "token_count": 500, "cost_usd": 0.002,
            "status": "ok",
            "output_snippet": "根因是配置残留导致 TOML 损坏，建议 SHA-256 校验 + 原子替换回滚。",
            "evidence_refs": [{"doc_id": "kb-sandbox-config-sync-v3", "chunk_index": 7,
                               "relevance_score": 0.92}],
        }


class ScenarioRunner:
    def __init__(self, agent: AgentExecutor):
        self.agent = agent

    def run(self, scenario: Scenario) -> tuple[Trajectory, dict]:
        from .evaluators.metrics import compute_all_metrics

        started = time.time()
        spans: list[Span] = []
        tokens = 0
        cost = 0.0
        evidence_refs: list[EvidenceRef] = []

        ctx = scenario.build_execution_context()
        if scenario.golden_trajectory_hints.must_include_tool_sequence:
            ctx.setdefault("_golden_tools",
                           scenario.golden_trajectory_hints.must_include_tool_sequence)

        for turn in self.agent.run_stream(
            user_prompt=scenario.input.user_prompt,
            context=ctx,
            tools_whitelist=scenario.tools_whitelist,
            seed=scenario.seed,
        ):
            span = Span.from_turn(turn, parent=spans[-1] if spans else None)
            spans.append(span)
            tokens += span.token_count
            cost += span.cost_usd
            if turn.get("evidence_refs"):
                evidence_refs.extend(EvidenceRef(**r) for r in turn["evidence_refs"])

        traj = Trajectory(
            trace_id=f"tr_{scenario.id}",
            started_at=started,
            ended_at=time.time(),
            total_token_count=tokens,
            total_cost_usd=cost,
            spans=spans,
            evidence_bank_refs=evidence_refs,
        )
        metrics = compute_all_metrics(traj, scenario)
        return traj, metrics
