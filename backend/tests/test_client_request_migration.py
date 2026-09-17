from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/20260906_0017_client_request_logs.py"
    )
    spec = importlib.util.spec_from_file_location("client_request_logs_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_client_request_log_migration_is_linear_and_complete(monkeypatch) -> None:
    migration = _load_migration()
    created_tables: list[str] = []
    created_indexes: list[tuple[str, str, tuple[str, ...]]] = []

    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *_columns, **_kwargs: created_tables.append(name),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, **_kwargs: created_indexes.append(
            (name, table, tuple(columns))
        ),
    )

    migration.upgrade()

    assert migration.down_revision == "20260905_0016"
    assert created_tables == ["client_request_logs"]
    assert {name for name, _table, _columns in created_indexes} == {
        "ix_client_request_logs_tenant_created",
        "ix_client_request_logs_tenant_user_created",
        "ix_client_request_logs_platform_created",
        "ix_client_request_logs_request_id",
    }


def test_client_request_log_migration_downgrade_removes_indexes_before_table(monkeypatch) -> None:
    migration = _load_migration()
    operations: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, **_kwargs: operations.append(f"index:{name}"),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda name: operations.append(f"table:{name}"),
    )

    migration.downgrade()

    assert operations[-1] == "table:client_request_logs"
    assert len(operations) == 5
