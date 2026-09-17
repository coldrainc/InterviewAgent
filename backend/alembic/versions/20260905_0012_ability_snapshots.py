from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0012"
down_revision = "20260905_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_ability_snapshots",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("goal_id", UuidString(), sa.ForeignKey("learning_goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dimensions_json", JsonDict(), nullable=False),
        sa.Column("evidence_json", JsonDict(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_learning_ability_owner_created",
        "learning_ability_snapshots",
        ["tenant_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("learning_ability_snapshots")
