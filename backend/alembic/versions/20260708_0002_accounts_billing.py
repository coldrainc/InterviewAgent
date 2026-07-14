from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260708_0002"
down_revision = "20260704_0001"
branch_labels = None
depends_on = None


def _json_type():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trial_uses_remaining", sa.Integer(), nullable=False),
        sa.Column("credit_balance_micros", sa.BigInteger(), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_user_accounts_tenant_user"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_accounts_tenant_email"),
    )
    op.create_index(
        "ix_user_accounts_tenant_created",
        "user_accounts",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("balance_after_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_credit_ledger_tenant_user_created",
        "credit_ledger",
        ["tenant_id", "user_id", "created_at"],
    )
    op.create_index("ix_credit_ledger_external_order", "credit_ledger", ["external_order_id"])

    op.create_table(
        "recharge_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_provider", sa.String(length=64), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "external_order_id", name="uq_recharge_orders_external"),
    )
    op.create_index(
        "ix_recharge_orders_tenant_user_created",
        "recharge_orders",
        ["tenant_id", "user_id", "created_at"],
    )

    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_credits_micros", sa.BigInteger(), nullable=False),
        sa.Column("trial_used", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_usage_records_tenant_user_created",
        "usage_records",
        ["tenant_id", "user_id", "created_at"],
    )
    op.create_index("ix_usage_records_session", "usage_records", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_records_session", table_name="usage_records")
    op.drop_index("ix_usage_records_tenant_user_created", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index("ix_recharge_orders_tenant_user_created", table_name="recharge_orders")
    op.drop_table("recharge_orders")
    op.drop_index("ix_credit_ledger_external_order", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_tenant_user_created", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_index("ix_user_accounts_tenant_created", table_name="user_accounts")
    op.drop_table("user_accounts")
