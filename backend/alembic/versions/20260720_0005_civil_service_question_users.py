from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260720_0005"
down_revision = "20260720_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "civil_service_questions",
        sa.Column("user_id", sa.String(length=128), nullable=False, server_default="anonymous"),
    )
    op.drop_constraint("uq_civil_service_questions_hash", "civil_service_questions", type_="unique")
    op.create_unique_constraint(
        "uq_civil_service_questions_user_hash",
        "civil_service_questions",
        ["tenant_id", "user_id", "content_hash"],
    )
    op.drop_index("ix_civil_service_questions_year_subject", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_type", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_updated", table_name="civil_service_questions")
    op.create_index(
        "ix_civil_service_questions_year_subject",
        "civil_service_questions",
        ["tenant_id", "user_id", "exam_year", "subject"],
    )
    op.create_index(
        "ix_civil_service_questions_type",
        "civil_service_questions",
        ["tenant_id", "user_id", "question_type"],
    )
    op.create_index(
        "ix_civil_service_questions_updated",
        "civil_service_questions",
        ["tenant_id", "user_id", "updated_at"],
    )
    op.alter_column("civil_service_questions", "user_id", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_civil_service_questions_updated", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_type", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_year_subject", table_name="civil_service_questions")
    op.drop_constraint("uq_civil_service_questions_user_hash", "civil_service_questions", type_="unique")
    op.create_unique_constraint(
        "uq_civil_service_questions_hash",
        "civil_service_questions",
        ["tenant_id", "content_hash"],
    )
    op.create_index(
        "ix_civil_service_questions_year_subject",
        "civil_service_questions",
        ["tenant_id", "exam_year", "subject"],
    )
    op.create_index(
        "ix_civil_service_questions_type",
        "civil_service_questions",
        ["tenant_id", "question_type"],
    )
    op.create_index(
        "ix_civil_service_questions_updated",
        "civil_service_questions",
        ["tenant_id", "updated_at"],
    )
    op.drop_column("civil_service_questions", "user_id")
