from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RevisionProposal:
    reason: str
    trigger: dict[str, Any]
    diff: dict[str, Any]


class RevisionPolicy:
    def propose(self, *, tasks: list[Any], runs: dict, daily_minutes: int, dimensions: dict) -> RevisionProposal | None:
        unlocked = [task for task in tasks if not bool((task.link_payload_json or {}).get("locked"))]
        if not unlocked:
            return None
        estimated = sum(int((task.link_payload_json or {}).get("estimated_minutes") or 20) for task in unlocked)
        if estimated > daily_minutes:
            removable = sorted(unlocked, key=lambda task: (bool(task.critical), -task.sort_order))
            deferred = []
            remaining = estimated
            for task in removable:
                if remaining <= daily_minutes:
                    break
                deferred.append(str(task.id))
                remaining -= int((task.link_payload_json or {}).get("estimated_minutes") or 20)
            return RevisionProposal(
                reason=f"今日任务预计 {estimated} 分钟，超过目标预算 {daily_minutes} 分钟",
                trigger={"type": "overload", "estimated_minutes": estimated, "daily_minutes": daily_minutes},
                diff={"defer_task_ids": deferred, "before_minutes": estimated, "after_minutes": remaining},
            )
        blocked = [task for task in unlocked if getattr(runs.get(task.id), "status", "") == "blocked"]
        if len(blocked) >= 2:
            return RevisionProposal(
                reason="存在多个验证失败任务，建议先降低强度并增加诊断",
                trigger={"type": "repeated_failure", "blocked_count": len(blocked)},
                diff={"defer_task_ids": [str(task.id) for task in blocked[1:]], "diagnostic_for": str(blocked[0].id)},
            )
        weak = sorted(
            ((name, data) for name, data in dimensions.items() if isinstance(data, dict)),
            key=lambda item: item[1].get("score", 100),
        )
        if weak and weak[0][1].get("score", 100) < 60:
            return RevisionProposal(
                reason=f"能力快照显示「{weak[0][0]}」得分偏低",
                trigger={"type": "weak_dimension", "dimension": weak[0][0], "score": weak[0][1].get("score")},
                diff={"prioritize_dimension": weak[0][0]},
            )
        return None
