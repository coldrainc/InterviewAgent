from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260720_0006"
down_revision = "20260720_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "civil_service_questions",
        sa.Column("practice_category", sa.String(length=64), nullable=False, server_default="civil_service"),
    )
    op.create_index(
        "ix_civil_service_questions_category",
        "civil_service_questions",
        ["tenant_id", "user_id", "practice_category"],
    )
    op.alter_column("civil_service_questions", "practice_category", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_civil_service_questions_category", table_name="civil_service_questions")
    op.drop_column("civil_service_questions", "practice_category")
