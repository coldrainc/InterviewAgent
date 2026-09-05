"""四大类指标汇总：任务完成度 / 过程合理性 / 效率成本 / 安全合规。"""

from __future__ import annotations

from collections import Counter

from ..schema import Scenario, Trajectory, Span, SpanType

from .deterministic import evaluate_assertions
from .trajectory import evaluate_trajectory


def compute_all_metrics(traj: Trajectory, scenario: Scenario) -> dict:
    # --- 1. 任务完成度
    assertion_res = evaluate_assertions(scenario, traj)
    task_success_rate = (assertion_res["passed"] / assertion_res["total"]) if assertion_res["total"] else 0.0

    # final answer 存在性（至少有一个 final_answer span）
    final_exists = any(s.type == SpanType.FINAL_ANSWER for s in traj.spans)
    final_status = next((s for s in reversed(traj.spans) if s.type == SpanType.FINAL_ANSWER), None)
    faithfulness_simple = 0.0
    if final_exists and final_status:
        # 简化 faithfulness：evidence ref 数量 / 回答中陈述数量（按句号分句估算）
        stmts = [p for p in final_status.output_snippet.split("。") if p.strip()]
        if stmts:
            faithfulness_simple = min(1.0, len(traj.evidence_bank_refs) / max(1, len(stmts)))

    # --- 2. 过程合理性（trajectory 指标）
    traj_metrics = evaluate_trajectory(scenario, traj)

    # 工具重复率（同一个工具循环出现≥3次）
    tool_seq = [s.tool_name for s in traj.spans if s.type == SpanType.TOOL_CALL]
    dup_count = sum(1 for _, c in Counter(tool_seq).items() if c >= 3)
    tool_repetition_rate = dup_count / len(tool_seq) if tool_seq else 0.0

    # --- 3. 效率与成本
    tool_calls = [s for s in traj.spans if s.type == SpanType.TOOL_CALL]
    reasoning = [s for s in traj.spans if s.type == SpanType.LLM_REASONING]
    total_steps = len(tool_calls) + len(reasoning)
    total_ms = sum(s.duration_ms for s in traj.spans)
    avg_step_ms = (total_ms / total_steps) if total_steps else 0.0

    # --- 4. 安全合规
    error_tools = sum(1 for s in tool_calls if s.status.value == "error")
    error_rate = error_tools / len(tool_calls) if tool_calls else 0.0
    # PII / forbidden 检测：简单的断言覆盖，这里仅输出 hook
    pii_suspicious_count = 0  # 实际项目可接 Presidio

    metrics = {
        # 完成度
        "task_success_rate": round(task_success_rate, 3),
        "assertion_result": assertion_res,
        "final_answer_exists": final_exists,
        "faithfulness_simple": round(faithfulness_simple, 3),
        # 过程
        **traj_metrics,
        "tool_repetition_rate": round(tool_repetition_rate, 3),
        # 效率成本
        "total_steps": total_steps,
        "avg_step_ms": round(avg_step_ms, 1),
        "total_token_count": traj.total_token_count,
        "total_cost_usd": round(traj.total_cost_usd, 5),
        # 安全
        "tool_error_rate": round(error_rate, 3),
        "pii_suspicious_count": pii_suspicious_count,
    }
    return metrics
