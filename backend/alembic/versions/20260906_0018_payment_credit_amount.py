from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260906_0018"
down_revision = "20260906_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recharge_orders",
        sa.Column("credit_amount_micros", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE recharge_orders SET credit_amount_micros = amount_micros WHERE credit_amount_micros = 0")
    op.alter_column("recharge_orders", "credit_amount_micros", server_default=None)


def downgrade() -> None:
    op.drop_column("recharge_orders", "credit_amount_micros")
