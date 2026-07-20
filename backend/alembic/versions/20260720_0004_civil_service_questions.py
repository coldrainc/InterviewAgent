from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260720_0004"
down_revision = "20260710_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "civil_service_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="manual"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("exam_year", sa.Integer(), nullable=False),
        sa.Column("exam_name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("choices_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "content_hash", name="uq_civil_service_questions_hash"),
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


def downgrade() -> None:
    op.drop_index("ix_civil_service_questions_updated", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_type", table_name="civil_service_questions")
    op.drop_index("ix_civil_service_questions_year_subject", table_name="civil_service_questions")
    op.drop_table("civil_service_questions")
