from __future__ import annotations

from typing import Any


def infer_task_type(*, link_type: str | None, simulation: bool, source: str | None) -> str:
    normalized = str(link_type or "").strip().lower()
    if normalized == "interview" or simulation:
        return "interview"
    if normalized == "practice":
        return "practice"
    if normalized in {"knowledge", "material"}:
        return "material"
    if normalized == "checkin" or source == "checkin":
        return "checkin"
    return "review"


def task_status(*, done: bool, elapsed_minutes: int, metadata: dict[str, Any]) -> str:
    if done:
        return "completed"
    latest = dict((metadata.get("learning_harness") or {}).get("latest_receipt") or {})
    if latest.get("current_status") in {"blocked", "todo", "in_progress"}:
        return str(latest["current_status"])
    return "in_progress" if elapsed_minutes > 0 else "todo"


def primary_action(task_type: str, *, done: bool, actionable: bool) -> dict[str, str]:
    if done:
        return {"command": "reopen", "label": "重新打开"}
    labels = {
        "interview": "开始模拟",
        "practice": "开始刷题",
        "material": "查看资料",
    }
    if task_type in labels:
        return {"command": "start", "label": labels[task_type]}
    return {"command": "start" if actionable else "complete", "label": "开始任务" if actionable else "完成任务"}


def project_task(task: Any, progress: Any | None, *, run: Any | None = None, receipt: Any | None = None) -> dict[str, Any]:
    metadata = dict(getattr(progress, "metadata_json", None) or {})
    latest = dict(getattr(receipt, "receipt_json", None) or {})
    if not latest:
        latest = dict((metadata.get("learning_harness") or {}).get("latest_receipt") or {})
    verification = dict(latest.get("verification") or {})
    done = bool(getattr(progress, "done", False))
    elapsed = int(getattr(progress, "elapsed_minutes", 0) or 0)
    link_type = str(getattr(task, "link_type", "none") or "none")
    task_type = infer_task_type(
        link_type=link_type,
        simulation=bool(getattr(task, "simulation", False)),
        source=str(getattr(task, "source", "plan") or "plan"),
    )
    status = str(getattr(run, "status", "") or "") or task_status(
        done=done, elapsed_minutes=elapsed, metadata=metadata
    )
    actionable = link_type != "none" or bool(getattr(task, "simulation", False))
    link_payload = dict(task.link_payload_json or {})
    # Navigation identifiers are derived from the owner-scoped task record, never
    # trusted from generated plan metadata.
    link_payload.update(
        {
            "plan_id": str(task.plan_id),
            "day_id": str(task.day_id),
            "task_id": str(task.id),
        }
    )
    return {
        "id": str(task.id),
        "task_key": task.task_key,
        "title": task.title,
        "sort_order": task.sort_order,
        "critical": bool(task.critical),
        "tags": list(task.tags_json or []),
        "source": task.source or "plan",
        "source_ref": task.source_ref,
        "reason": task.reason,
        "task_type": task_type,
        "link_type": link_type,
        "link_payload": link_payload,
        "locked": bool(link_payload.get("locked")),
        "deferred": bool(link_payload.get("deferred")),
        "done": done,
        "status": status,
        "version": int(getattr(run, "version", 0) or 0),
        "elapsed_minutes": elapsed,
        "mastery_score": getattr(progress, "mastery_score", None),
        "verification": verification or {"status": "not_run", "mode": "none"},
        "primary_action": primary_action(task_type, done=done, actionable=actionable),
    }
