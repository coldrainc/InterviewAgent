"""门禁决策逻辑：与 demos/harness 保持一致，但增加 GATE_ENABLED 止血开关 + DEFERRED_LLM_AS_PASS。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Decision:
    passed: bool
    reasons: list[str] = field(default_factory=list)


DEFAULT_GATES = {
    "test": {
        "task_success_rate": {"baseline_delta": -0.02},
        "tool_selection_acc": {"absolute": 0.85},
    },
    "agent": {
        "task_success_rate": {"baseline_delta": -0.02},
        "tool_selection_acc": {"baseline_delta": -0.03},
        "3d_overall": {"baseline_delta": -0.03},
        "total_cost_usd": {"baseline_delta_ratio": 0.15},
        "tool_error_rate": {"absolute": 0.05},
    },
    "release": {
        "task_success_rate": {"absolute": 0.90},
        "3d_overall": {"absolute": 0.70},
        "tool_error_rate": {"absolute": 0.02},
    },
}


def _get(m: dict, k: str):
    cur = m
    for p in k.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return int(cur) if isinstance(cur, bool) else cur


def decide(metrics: dict, baseline: dict, gate_level: str = "test", *,
           gates: dict | None = None,
           gate_enabled: bool = True,
           deferred_llm_as_pass: bool = False) -> Decision:
    if not gate_enabled:
        return Decision(passed=True, reasons=[
            "[OBSERVE MODE] 全局 GATE_ENABLED=false，门禁不阻断。"
        ])
    rules = (gates or DEFAULT_GATES).get(gate_level) or DEFAULT_GATES["test"]
    reasons: list[str] = []
    if deferred_llm_as_pass:
        reasons.append("[DEFERRED] LLM-Judge 延迟项全部按通过处理")

    smaller_better_keys = ("cost", "error_rate", "latency", "ms", "count",
                           "steps", "repetition")

    for k, rule in rules.items():
        v = _get(metrics, k)
        b = _get(baseline, k)
        if v is None:
            reasons.append(f"[SKIP] {k}：metrics 中缺失")
            continue

        if "baseline_delta" in rule and b is not None:
            try:
                delta = float(v) - float(b)
            except Exception:
                reasons.append(f"[SKIP] {k}: {v}/{b} 不是数值")
                continue
            th = float(rule["baseline_delta"])
            # 越小越好的指标 + delta 阈值为负时，反着理解
            smaller = any(kk in k for kk in smaller_better_keys)
            bad = delta < th if not smaller else delta > abs(th)
            if bad:
                reasons.append(
                    f"[FAIL] {k}: delta={delta:.4f} 阈值区间 {('<= '+str(th)) if not smaller else ('>= +'+str(abs(th)))}"
                    f" (new={v} baseline={b})"
                )
        if "baseline_delta_ratio" in rule and b:
            try:
                ratio = (float(v) - float(b)) / float(b)
            except Exception:
                continue
            th = float(rule["baseline_delta_ratio"])
            if ratio > th:
                reasons.append(
                    f"[FAIL] {k}: ratio_change={ratio:.3f} 超过阈值 {th:.3f}"
                    f" (new={v} baseline={b})"
                )
        if "absolute" in rule:
            th = float(rule["absolute"])
            smaller = any(kk in k for kk in smaller_better_keys)
            bad = float(v) < th if not smaller else float(v) > th
            if bad:
                reasons.append(
                    f"[FAIL] {k}: {v} {'<' if not smaller else '>'} 阈值 {th}"
                )

    passed = not any(r.startswith("[FAIL]") for r in reasons)
    return Decision(passed=passed, reasons=reasons)
