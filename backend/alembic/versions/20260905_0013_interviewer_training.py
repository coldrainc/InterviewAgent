from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0013"
down_revision = "20260905_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interviewer_kits",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target_role", sa.String(length=255), nullable=False),
        sa.Column("seniority", sa.String(length=128), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("dimensions_json", JsonDict(), nullable=False),
        sa.Column("questions_json", JsonDict(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_interviewer_kits_owner_updated", "interviewer_kits", ["tenant_id", "user_id", "updated_at"])
    op.add_column("interview_sessions", sa.Column("interviewer_kit_id", UuidString(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_interview_sessions_interviewer_kit",
            "interview_sessions",
            "interviewer_kits",
            ["interviewer_kit_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "interviewer_evidence",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("kit_id", UuidString(), sa.ForeignKey("interviewer_kits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UuidString(), sa.ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_key", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("signal", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "kit_id", "client_key", name="uq_interviewer_evidence_client_key"),
    )
    op.create_index("ix_interviewer_evidence_kit_created", "interviewer_evidence", ["kit_id", "created_at"])
    op.create_table(
        "training_drills",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("focus", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("question_ids_json", JsonDict(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_drills_owner_created", "training_drills", ["tenant_id", "user_id", "created_at"])
    op.create_table(
        "spaced_review_items",
        sa.Column("id", UuidString(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("question_id", UuidString(), sa.ForeignKey("practice_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("ease_score", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "question_id", name="uq_spaced_review_owner_question"),
    )
    op.create_index("ix_spaced_review_owner_due", "spaced_review_items", ["tenant_id", "user_id", "due_at"])


def downgrade() -> None:
    op.drop_table("spaced_review_items")
    op.drop_table("training_drills")
    op.drop_table("interviewer_evidence")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        foreign_keys = sa.inspect(bind).get_foreign_keys("interview_sessions")
        kit_foreign_key = next(
            (
                item
                for item in foreign_keys
                if item.get("constrained_columns") == ["interviewer_kit_id"]
            ),
            None,
        )
        naming_convention = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
        with op.batch_alter_table(
            "interview_sessions",
            naming_convention=naming_convention,
            recreate="always",
        ) as batch_op:
            if kit_foreign_key is not None:
                constraint_name = kit_foreign_key.get("name") or (
                    "fk_interview_sessions_interviewer_kit_id_interviewer_kits"
                )
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
            batch_op.drop_column("interviewer_kit_id")
    else:
        op.drop_constraint("fk_interview_sessions_interviewer_kit", "interview_sessions", type_="foreignkey")
        op.drop_column("interview_sessions", "interviewer_kit_id")
    op.drop_table("interviewer_kits")
