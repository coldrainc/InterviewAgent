from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SyncCursor:
    occurred_at: datetime
    event_id: uuid.UUID


def encode_cursor(occurred_at: datetime, event_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"at": occurred_at.isoformat(), "id": str(event_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value: str | None) -> SyncCursor | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return SyncCursor(
            occurred_at=datetime.fromisoformat(payload["at"]),
            event_id=uuid.UUID(payload["id"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid sync cursor") from exc
