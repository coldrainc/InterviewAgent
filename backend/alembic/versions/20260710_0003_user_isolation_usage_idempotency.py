from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0003"
down_revision = "20260708_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("user_id", sa.String(length=128), nullable=False, server_default="anonymous"),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("user_id", sa.String(length=128), nullable=False, server_default="anonymous"),
    )
    op.add_column(
        "memory_items",
        sa.Column("user_id", sa.String(length=128), nullable=False, server_default="anonymous"),
    )
    op.add_column(
        "usage_records",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )

    op.drop_index("ix_resumes_tenant_updated", table_name="resumes")
    op.drop_constraint("uq_resumes_tenant_content_hash", "resumes", type_="unique")
    op.create_unique_constraint(
        "uq_resumes_tenant_user_content_hash",
        "resumes",
        ["tenant_id", "user_id", "content_hash"],
    )
    op.create_index(
        "ix_resumes_tenant_user_updated",
        "resumes",
        ["tenant_id", "user_id", "updated_at"],
    )

    op.drop_index("ix_interview_sessions_tenant_updated", table_name="interview_sessions")
    op.create_index(
        "ix_interview_sessions_tenant_user_updated",
        "interview_sessions",
        ["tenant_id", "user_id", "updated_at"],
    )

    op.drop_index("ix_memory_items_tenant_created", table_name="memory_items")
    op.create_index(
        "ix_memory_items_tenant_user_created",
        "memory_items",
        ["tenant_id", "user_id", "created_at"],
    )

    op.create_unique_constraint(
        "uq_usage_records_idempotency_key",
        "usage_records",
        ["tenant_id", "idempotency_key"],
    )

    op.alter_column("resumes", "user_id", server_default=None)
    op.alter_column("interview_sessions", "user_id", server_default=None)
    op.alter_column("memory_items", "user_id", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_usage_records_idempotency_key", "usage_records", type_="unique")
    op.drop_column("usage_records", "idempotency_key")

    op.drop_index("ix_memory_items_tenant_user_created", table_name="memory_items")
    op.create_index("ix_memory_items_tenant_created", "memory_items", ["tenant_id", "created_at"])

    op.drop_index("ix_interview_sessions_tenant_user_updated", table_name="interview_sessions")
    op.create_index(
        "ix_interview_sessions_tenant_updated",
        "interview_sessions",
        ["tenant_id", "updated_at"],
    )

    op.drop_index("ix_resumes_tenant_user_updated", table_name="resumes")
    op.drop_constraint("uq_resumes_tenant_user_content_hash", "resumes", type_="unique")
    op.create_unique_constraint(
        "uq_resumes_tenant_content_hash",
        "resumes",
        ["tenant_id", "content_hash"],
    )
    op.create_index("ix_resumes_tenant_updated", "resumes", ["tenant_id", "updated_at"])

    op.drop_column("memory_items", "user_id")
    op.drop_column("interview_sessions", "user_id")
    op.drop_column("resumes", "user_id")
