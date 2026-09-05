"""失败模式 analyzers（AgentCompass 式 pluggable analyzer）。
每一个 analyzer 输入 trajectory，输出结构化的 failure mode 标签 + 证据 span 索引。
"""

from __future__ import annotations

from ..schema import Trajectory, Span, SpanType
from dataclasses import dataclass, field


@dataclass
class Finding:
    tag: str                          # 如 "tool_repetition_loop"
    severity: str                     # info / warning / error
    span_indices: list[int] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# 工具重复循环（同一个工具被调≥3次且输入几乎不变）
# ---------------------------------------------------------------------------

def detect_repetition(traj: Trajectory) -> list[Finding]:
    findings: list[Finding] = []
    tool_calls_with_idx = [
        (i, s) for i, s in enumerate(traj.spans)
        if s.type == SpanType.TOOL_CALL and s.tool_name
    ]
    from collections import defaultdict
    groups: dict[str, list[tuple[int, Span]]] = defaultdict(list)
    for i, s in tool_calls_with_idx:
        groups[s.tool_name].append((i, s))
    for name, items in groups.items():
        if len(items) >= 3:
            args = [frozenset(s.tool_args.items()) for _, s in items]
            if len(set(args)) <= max(1, len(args) // 3):  # 多数相同参数
                findings.append(Finding(
                    tag="tool_repetition_loop",
                    severity="warning",
                    span_indices=[i for i, _ in items],
                    description=f"工具 {name} 被多次重复调用且参数相同，疑似陷入循环。",
                ))
    return findings


# ---------------------------------------------------------------------------
# 延迟尖刺：单 span 耗时 > 平均 3x 且绝对超过 2s
# ---------------------------------------------------------------------------

def detect_latency_spikes(traj: Trajectory) -> list[Finding]:
    if not traj.spans:
        return []
    avg = sum(s.duration_ms for s in traj.spans) / len(traj.spans)
    threshold = max(2000, avg * 3)
    return [
        Finding(
            tag="latency_spike",
            severity="warning" if s.duration_ms < threshold * 2 else "error",
            span_indices=[i],
            description=f"{s.name} 耗时 {s.duration_ms:.0f}ms > 阈值 {threshold:.0f}ms。",
        )
        for i, s in enumerate(traj.spans) if s.duration_ms >= threshold
    ]


# ---------------------------------------------------------------------------
# 失败模式分类：把 span 的错误 / 截断自动打标签
# ---------------------------------------------------------------------------

FAILURE_MODE_TAGS = {
    SpanStatus.ERROR: "tool_execution_error",
    SpanStatus.TIMEOUT: "span_timeout",
    SpanStatus.TRUNCATED: "output_truncation",
}

def classify_failure_modes(traj: Trajectory) -> list[Finding]:
    findings: list[Finding] = []
    for i, s in enumerate(traj.spans):
        if s.status.value == "ok" or s.status.value == "skipped":
            continue
        tag = FAILURE_MODE_TAGS.get(s.status, "unknown_failure")
        findings.append(Finding(
            tag=tag, severity="error", span_indices=[i],
            description=f"{s.name} 状态={s.status.value} err={s.error_message or ''}",
        ))
    # 参数盲选：tool_call 但 tool_args 全空
    for i, s in enumerate(traj.spans):
        if s.type == SpanType.TOOL_CALL and not s.tool_args:
            findings.append(Finding(
                tag="parameter_blind_selection", severity="warning",
                span_indices=[i],
                description=f"工具 {s.tool_name} 调用未提供任何参数。",
            ))
    # 非法工具：scenario 有 whitelist 但调用了不在其中的
    return findings


# ---------------------------------------------------------------------------
# 组合入口
# ---------------------------------------------------------------------------

ALL_ANALYZERS = [detect_repetition, detect_latency_spikes, classify_failure_modes]

def analyze(traj: Trajectory) -> list[Finding]:
    findings: list[Finding] = []
    for fn in ALL_ANALYZERS:
        findings.extend(fn(traj))
    return findings


def findings_summary(findings: list[Finding]) -> dict:
    tags = Counter(f.tag for f in findings)
    sev = Counter(f.severity for f in findings)
    return {"count": len(findings), "by_tag": dict(tags), "by_severity": dict(sev)}
