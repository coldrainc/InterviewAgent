from __future__ import annotations

import time
from collections import Counter, deque
from functools import wraps
from threading import Lock

from interview_agent.learning.errors import IdempotencyConflictError, LearningConflictError, VersionConflictError


ALLOWED_ACTIONS = {"start", "complete", "reopen", "verify"}


class LearningCommandMetrics:
    """Low-cardinality runtime metrics. No user content or identifiers are retained."""

    def __init__(self, *, sample_limit: int = 2048) -> None:
        self._lock = Lock()
        self._counts: Counter[tuple[str, str]] = Counter()
        self._latencies: deque[float] = deque(maxlen=sample_limit)

    def record(self, *, action: str, outcome: str, duration_ms: float) -> None:
        safe_action = action if action in ALLOWED_ACTIONS else "unknown"
        with self._lock:
            self._counts[(safe_action, outcome)] += 1
            self._latencies.append(max(0.0, duration_ms))

    def snapshot(self) -> dict:
        with self._lock:
            counts = dict(self._counts)
            latencies = sorted(self._latencies)
        total = sum(counts.values())
        by_action = {
            action: sum(value for (candidate, _), value in counts.items() if candidate == action)
            for action in sorted({action for action, _ in counts})
        }
        by_outcome = {
            outcome: sum(value for (_, candidate), value in counts.items() if candidate == outcome)
            for outcome in sorted({outcome for _, outcome in counts})
        }
        accepted = by_outcome.get("succeeded", 0) + by_outcome.get("idempotent_replay", 0)
        conflicts = by_outcome.get("version_conflict", 0) + by_outcome.get("idempotency_conflict", 0)
        return {
            "commands": {
                "total": total,
                "by_action": by_action,
                "by_outcome": by_outcome,
                "success_rate": _rate(accepted, total),
                "conflict_rate": _rate(conflicts, total),
                "verification_rejection_rate": _rate(by_outcome.get("verification_rejected", 0), total),
                "idempotent_replay_total": by_outcome.get("idempotent_replay", 0),
            },
            "latency_ms": {
                "sample_count": len(latencies),
                "average": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "max": round(latencies[-1], 2) if latencies else 0.0,
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._latencies.clear()


learning_command_metrics = LearningCommandMetrics()


def observe_learning_command(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        started = time.perf_counter()
        action = str(kwargs.get("action") or "unknown").strip().lower()
        outcome = "failed"
        try:
            result = await function(*args, **kwargs)
            if result.get("idempotent_replay"):
                outcome = "idempotent_replay"
            elif result.get("receipt", {}).get("accepted") is False:
                outcome = "verification_rejected"
            else:
                outcome = "succeeded"
            return result
        except VersionConflictError:
            outcome = "version_conflict"
            raise
        except IdempotencyConflictError:
            outcome = "idempotency_conflict"
            raise
        except LearningConflictError:
            outcome = "learning_conflict"
            raise
        except (LookupError, ValueError):
            outcome = "invalid_request"
            raise
        finally:
            learning_command_metrics.record(
                action=action,
                outcome=outcome,
                duration_ms=(time.perf_counter() - started) * 1000,
            )

    return wrapped


def _rate(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int((len(values) - 1) * percentile)))
    return round(values[index], 2)
