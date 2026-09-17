from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[redacted]"
SENSITIVE_KEY_PARTS = {
    "answer",
    "authorization",
    "content",
    "credential",
    "feedback",
    "message",
    "password",
    "payment",
    "payload",
    "prompt",
    "question",
    "recommendation",
    "resume",
    "secret",
    "suggestion",
    "summary",
    "text",
    "token",
    "transcript",
    "weakness",
}


def sanitize_telemetry(value: Any, *, depth: int = 0) -> Any:
    """Keep trace structure while removing user content, credentials and payment data."""
    if depth >= 8:
        return "[truncated]"
    if isinstance(value, Mapping):
        return {
            str(key)[:128]: REDACTED if _sensitive_key(str(key)) else sanitize_telemetry(item, depth=depth + 1)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_telemetry(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return value[:500]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:200]


def sanitize_error_message(value: str | None) -> str | None:
    if not value:
        return None
    return "operation failed; inspect server logs with the correlated request or trace id"


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
