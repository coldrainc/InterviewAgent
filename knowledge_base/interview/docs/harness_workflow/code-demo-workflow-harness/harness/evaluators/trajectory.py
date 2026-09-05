"""过程性评测：工具正确性 + trajectory 三维度评分（TRACE 论文思想）。

TRACE 论文（ICML 2026）提出三维度：
  - Validity（有效性）：步骤是否对事实知识（evidence bank）保持一致
  - Efficiency（效率）：步数、工具调用开销
  - Adaptivity（适应性）：遇到错误后是否能纠正
"""

from __future__ import annotations

from collections import Counter

from ..schema import Scenario, Trajectory, Span, SpanType


# ---------------------------------------------------------------------------
# 工具层面：选择正确率 + 参数正确率 + 顺序满足度（TRAJECT-Bench 思路）
# ---------------------------------------------------------------------------

def tool_selection_accuracy(traj: Trajectory, golden_tools: list[str]) -> float:
    """比较轨迹实际调的工具和期望（最小子序列匹配 + 精确匹配混合）。
    简单实现：按顺序比对 golden_tools，命中的比例。"""
    if not golden_tools:
        return 1.0
    actual = [s.tool_name for s in traj.spans
              if s.type == SpanType.TOOL_CALL and s.tool_name]
    matches = 0
    it = iter(actual)
    for expected in golden_tools:
        if any(a == expected for a in it):
            matches += 1
    return matches / len(golden_tools)


def parameter_correctness(traj: Trajectory) -> float:
    """参数是否有明显"盲选"：空参数、参数全部是默认值、无参数的比例反向。
    简化实现：非空参数的 tool_call 占比。"""
    tool_calls = [s for s in traj.spans if s.type == SpanType.TOOL_CALL]
    if not tool_calls:
        return 0.0
    meaningful = sum(1 for s in tool_calls if s.tool_args)
    return meaningful / len(tool_calls)


def tool_order_satisfaction(traj: Trajectory, ordered: list[str]) -> float:
    """期望的工具顺序是否按序出现（允许插入其他工具）。"""
    if not ordered:
        return 1.0
    actual = [s.tool_name for s in traj.spans if s.type == SpanType.TOOL_CALL]
    pos = 0
    ok = 0
    for name in ordered:
        while pos < len(actual) and actual[pos] != name:
            pos += 1
        if pos < len(actual):
            ok += 1
            pos += 1
    return ok / len(ordered)


# ---------------------------------------------------------------------------
# TRACE 三维度
# ---------------------------------------------------------------------------

def validity_score(traj: Trajectory) -> float:
    """有效性：evidence bank 是否支撑最终回答，且步骤间无明显矛盾。
    简化指标：
      1) final answer 必须对应 evidence ref（数量>0 得 0.5 分）
      2) 没有工具 error 占比（除最后重试外）
    """
    score = 0.0
    if traj.evidence_bank_refs:
        score += 0.5
    tool_calls = [s for s in traj.spans if s.type == SpanType.TOOL_CALL]
    if tool_calls:
        ok = sum(1 for s in tool_calls if s.status.value == "ok")
        score += 0.5 * (ok / len(tool_calls))
    else:
        score += 0.5  # 无工具的任务不扣分
    return score


def efficiency_score(traj: Trajectory) -> float:
    """效率：步数越少越优；token / cost 越低越优。做归一化打分 0~1。
    用经验阈值：10 步以内满分，每超一步扣 0.1。"""
    reasoning = [s for s in traj.spans if s.type == SpanType.LLM_REASONING]
    steps = len(reasoning)
    s1 = max(0.0, 1.0 - max(0, steps - 10) * 0.1)

    # token：10k 以内满分，每超 1k 扣 0.05
    s2 = max(0.0, 1.0 - max(0, traj.total_token_count - 10000) / 1000 * 0.05)

    return round(0.5 * s1 + 0.5 * s2, 3)


def adaptivity_score(traj: Trajectory) -> float:
    """适应性：遇到 error 后是否重试/换工具。
    简化：error span 后相邻 span 是否为有效尝试。"""
    errors = [i for i, s in enumerate(traj.spans) if s.status.value == "error"]
    if not errors:
        return 1.0  # 无错误，适应性不扣分
    adapted = 0
    for i in errors:
        if i + 1 < len(traj.spans):
            nxt = traj.spans[i + 1]
            if nxt.status.value == "ok" and nxt.type in (
                    SpanType.LLM_REASONING, SpanType.TOOL_CALL):
                adapted += 1
    return round(adapted / len(errors), 3)


def trajectory_3d_score(traj: Trajectory) -> dict:
    v = validity_score(traj)
    e = efficiency_score(traj)
    a = adaptivity_score(traj)
    return {
        "validity": v, "efficiency": e, "adaptivity": a,
        "overall": round((v + e + a) / 3, 3),
    }


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def evaluate_trajectory(scenario: Scenario, traj: Trajectory) -> dict:
    ordered = scenario.golden_trajectory_hints.must_include_tool_sequence
    return {
        "tool_selection_acc": tool_selection_accuracy(traj, ordered),
        "parameter_correctness": parameter_correctness(traj),
        "tool_order_satisfaction": tool_order_satisfaction(traj, ordered),
        **{f"3d_{k}": v for k, v in trajectory_3d_score(traj).items()},
    }
