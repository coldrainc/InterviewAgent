from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/20260905_0015_civil_service_question_uuid.py"
    )
    spec = importlib.util.spec_from_file_location("civil_service_question_uuid_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_civil_service_uuid_migration_uses_explicit_postgres_cast(monkeypatch) -> None:
    migration = _load_migration()
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    migration.upgrade()

    assert len(calls) == 1
    assert calls[0][0] == ("civil_service_questions", "id")
    assert calls[0][1]["postgresql_using"] == "id::uuid"


def test_civil_service_uuid_migration_is_noop_on_sqlite(monkeypatch) -> None:
    migration = _load_migration()
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    migration.upgrade()

    assert calls == []
