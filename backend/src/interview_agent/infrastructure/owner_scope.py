"""Stable, non-identifying namespaces for owner-scoped persisted data."""

from __future__ import annotations

import hashlib


def owner_namespace(tenant_id: str, user_id: str) -> str:
    """Return a filesystem/object-store-safe namespace without exposing owner IDs."""
    identity = f"{tenant_id}\x1f{user_id}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:32]
