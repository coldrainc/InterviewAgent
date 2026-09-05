"""回归门禁：把本次 metrics 与 baseline 对比，按阈值决定 Pass/Fail。

支持两种规则：
  - baseline_delta：本次相对基线的变化（负值表下降）
  - absolute：绝对阈值（如 tool_acc ≥ 0.90）
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


# PR / Nightly / Release 各层的阈值。按需调整。
DEFAULT_GATES = {
    "test": {
        "task_success_rate": {"baseline_delta": -0.02},
        "tool_selection_acc": {"absolute": 0.85},
    },
    "agent": {
        "task_success_rate": {"baseline_delta": -0.02},
        "tool_selection_acc": {"baseline_delta": -0.03},
        "3d_overall": {"baseline_delta": -0.03},
        "total_cost_usd": {"baseline_delta_ratio": 0.15},  # 成本相对涨 >15% fail
        "tool_error_rate": {"absolute": 0.05},               # 错误率 >5% fail
    },
    "release": {
        "task_success_rate": {"absolute": 0.90},
        "3d_overall": {"absolute": 0.70},
        "tool_error_rate": {"absolute": 0.02},
    },
}


@dataclass
class GateDecision:
    passed: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"passed": self.passed, "reasons": self.reasons}


def _metric_value(metrics: dict, name: str):
    """支持嵌套读取，例如 'assertion_result.passed'。"""
    cur = metrics
    for p in name.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    if isinstance(cur, bool):
        return int(cur)
    return cur


def decide(
    metrics: dict,
    baseline: dict,
    gate_level: str = "test",
    gates: dict | None = None,
) -> GateDecision:
    gates = gates or DEFAULT_GATES
    rules = gates.get(gate_level) or DEFAULT_GATES["test"]
    reasons: list[str] = []

    for metric_name, rule in rules.items():
        new_v = _metric_value(metrics, metric_name)
        base_v = _metric_value(baseline, metric_name)
        if new_v is None:
            reasons.append(f"[SKIP] {metric_name}：metrics 中缺失，跳过")
            continue

        if "baseline_delta" in rule and base_v is not None:
            delta = float(new_v) - float(base_v)
            th = float(rule["baseline_delta"])
            if delta < th:
                reasons.append(
                    f"[FAIL] {metric_name}: delta={delta:.3f} 阈值基线差{th:.3f} "
                    f"(new={new_v} baseline={base_v})"
                )

        if "baseline_delta_ratio" in rule and base_v:
            ratio = (float(new_v) - float(base_v)) / float(base_v)
            th = float(rule["baseline_delta_ratio"])
            # 成本/耗时/错误率是"涨超阈值即失败"
            if ratio > th:
                reasons.append(
                    f"[FAIL] {metric_name}: ratio_change={ratio:.3f} 超过阈值{th:.3f} "
                    f"(new={new_v} baseline={base_v})"
                )

        if "absolute" in rule:
            # 区分"越大越好"和"越小越好"：成本/错误率/耗时越小越好，其他越大越好
            smaller_is_better = any(key in metric_name for key in
                                    ("cost", "error_rate", "latency", "ms", "count", "steps"))
            th = float(rule["absolute"])
            if smaller_is_better:
                if float(new_v) > th:
                    reasons.append(
                        f"[FAIL] {metric_name}: {new_v} > 上限 {th}"
                    )
            else:
                if float(new_v) < th:
                    reasons.append(
                        f"[FAIL] {metric_name}: {new_v} < 下限 {th}"
                    )

    passed = not any(r.startswith("[FAIL]") for r in reasons)
    if passed and not reasons:
        reasons.append("[PASS] 全部规则满足")
    return GateDecision(passed=passed, reasons=reasons)


# ---------------------------------------------------------------------------
# Baseline 读写
# ---------------------------------------------------------------------------

def load_baseline(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_baseline(path: str | Path, aggregated: dict) -> None:
    Path(path).write_text(json.dumps(aggregated, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def aggregate_scenario_metrics(per_scenario: dict[str, dict]) -> dict:
    """把多个 scenario 的指标聚合成整体 baseline（平均）。"""
    # 数字指标取平均，非数字丢弃
    keys = set()
    for m in per_scenario.values():
        keys.update(k for k, v in m.items() if isinstance(v, (int, float, bool)))
    agg: dict = {}
    for k in keys:
        vals = [m[k] for m in per_scenario.values() if k in m]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            agg[k] = round(sum(vals) / len(vals), 5)
    agg["scenario_count"] = len(per_scenario)
    return agg
