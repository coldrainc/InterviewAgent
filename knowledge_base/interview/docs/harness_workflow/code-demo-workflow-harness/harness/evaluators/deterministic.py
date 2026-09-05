"""确定性断言 evaluator：不调用大模型，便宜又稳。"""

from __future__ import annotations

from ..schema import Scenario, Assertion, Trajectory, Span, SpanType


def tool_called(traj: Trajectory, tool_name: str, args_match: dict | None = None) -> bool:
    for s in traj.spans:
        if s.type == SpanType.TOOL_CALL and s.tool_name == tool_name:
            if not args_match:
                return True
            if all(s.tool_args.get(k) == v for k, v in args_match.items()):
                return True
    return False


def no_forbidden_tool(traj: Trajectory, forbidden: list[str]) -> bool:
    for s in traj.spans:
        if s.type == SpanType.TOOL_CALL and s.tool_name in forbidden:
            return False
    return True


def max_steps(traj: Trajectory, limit: int) -> bool:
    reasoning_or_tool = [s for s in traj.spans
                         if s.type in (SpanType.LLM_REASONING, SpanType.TOOL_CALL)]
    return len(reasoning_or_tool) <= limit


def final_answer_contains(traj: Trajectory, answers: list[str]) -> bool:
    final = next((s for s in reversed(traj.spans) if s.type == SpanType.FINAL_ANSWER), None)
    if not final:
        return False
    text = final.output_snippet
    return all(ans in text for ans in answers)


def cost_below(traj: Trajectory, max_usd: float) -> bool:
    return traj.total_cost_usd <= max_usd


# ---------------------------------------------------------------------------
# 统一入口：跑 scenario 上所有 assertions 逐项出结果
# ---------------------------------------------------------------------------

def evaluate_assertions(scenario: Scenario, traj: Trajectory) -> dict:
    results: list[dict] = []
    passed = 0
    for a in scenario.assertions:
        one = {"type": a.type.value, "passed": False, "detail": ""}
        try:
            if a.type.value == "tool_called":
                one["passed"] = tool_called(traj, a.tool_name or "", a.args_match)
                one["detail"] = f"tool={a.tool_name} args_match={a.args_match}"
            elif a.type.value == "no_forbidden_tool":
                one["passed"] = no_forbidden_tool(traj, a.forbidden_tools or [])
            elif a.type.value == "max_steps":
                one["passed"] = max_steps(traj, int(a.value or 999))
                one["detail"] = f"limit={a.value}"
            elif a.type.value == "answer_contains":
                one["passed"] = final_answer_contains(traj, a.answers or [])
                one["detail"] = f"must_contain={a.answers}"
            elif a.type.value == "cost_below":
                one["passed"] = cost_below(traj, float(a.value or 1e9))
                one["detail"] = f"limit_usd={a.value}"
            elif a.type.value == "llm_judge":
                # 延迟处理：此处标记为 deferred，由 llm_judge.py 单独跑
                one["passed"] = True
                one["deferred"] = True
                one["detail"] = f"criteria={a.criteria[:60] if a.criteria else ''}..."
        except Exception as e:  # pragma: no cover - 防御性
            one["detail"] = f"evaluator_error: {e}"
        if one["passed"]:
            passed += 1
        results.append(one)

    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "assertions": results,
    }
