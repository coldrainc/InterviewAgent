from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0016"
down_revision = "20260905_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_policies",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("input_usd_per_1m", sa.String(length=32), nullable=True),
        sa.Column("output_usd_per_1m", sa.String(length=32), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "model_id", name="uq_model_policies_tenant_model"),
    )
    op.create_index("ix_model_policies_tenant_updated", "model_policies", ["tenant_id", "updated_at"])
    op.create_table(
        "subscription_plans",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_micros", sa.BigInteger(), nullable=False),
        sa.Column("credits_micros", sa.BigInteger(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("features_json", JsonDict(), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_subscription_plans_tenant_code"),
    )
    op.create_index("ix_subscription_plans_tenant_sort", "subscription_plans", ["tenant_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_subscription_plans_tenant_sort", table_name="subscription_plans")
    op.drop_table("subscription_plans")
    op.drop_index("ix_model_policies_tenant_updated", table_name="model_policies")
    op.drop_table("model_policies")
