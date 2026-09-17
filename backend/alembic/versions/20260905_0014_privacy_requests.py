from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0014"
down_revision = "20260905_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_deletion_requests",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("scope_json", JsonDict(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_data_deletion_owner_status",
        "data_deletion_requests",
        ["tenant_id", "user_id", "status"],
    )
    op.create_index(
        "ix_data_deletion_status_execute",
        "data_deletion_requests",
        ["status", "execute_after"],
    )


def downgrade() -> None:
    op.drop_table("data_deletion_requests")
