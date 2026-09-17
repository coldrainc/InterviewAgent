from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import UuidString


revision = "20260906_0017"
down_revision = "20260905_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_request_logs",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("auth_platform", sa.String(length=32), nullable=False),
        sa.Column("client_platform", sa.String(length=32), nullable=False),
        sa.Column("client_version", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("platform_matched", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_request_logs_tenant_created", "client_request_logs", ["tenant_id", "created_at"])
    op.create_index("ix_client_request_logs_tenant_user_created", "client_request_logs", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_client_request_logs_platform_created", "client_request_logs", ["client_platform", "created_at"])
    op.create_index("ix_client_request_logs_request_id", "client_request_logs", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_client_request_logs_request_id", table_name="client_request_logs")
    op.drop_index("ix_client_request_logs_platform_created", table_name="client_request_logs")
    op.drop_index("ix_client_request_logs_tenant_user_created", table_name="client_request_logs")
    op.drop_index("ix_client_request_logs_tenant_created", table_name="client_request_logs")
    op.drop_table("client_request_logs")
