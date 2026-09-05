from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260904_0009"
down_revision = "20260720_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_plans",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("plan_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_root", sa.Text(), nullable=False),
        sa.Column("source_documents_json", JsonDict(), nullable=False),
        sa.Column("commercial_positioning_json", JsonDict(), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "plan_key", name="uq_review_plans_tenant_user_key"),
    )
    op.create_index("ix_review_plans_tenant_updated", "review_plans", ["tenant_id", "user_id", "updated_at"])

    op.create_table(
        "review_plan_phases",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("phase_key", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("range_label", sa.String(length=128), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_plan_phases_plan", ondelete="CASCADE"),
    )
    op.create_index("ix_review_plan_phases_plan", "review_plan_phases", ["plan_id", "sort_order"])

    op.create_table(
        "review_plan_days",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("day_key", sa.String(length=32), nullable=False),
        sa.Column("day_label", sa.String(length=64), nullable=False),
        sa.Column("phase_key", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("acceptance", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_plan_days_plan", ondelete="CASCADE"),
    )

    op.create_table(
        "review_plan_tasks",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("day_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("task_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("tags_json", JsonDict(), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("simulation", sa.Boolean(), nullable=False),
        sa.Column("docs_json", JsonDict(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_plan_tasks_plan", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["day_id"], ["review_plan_days.id"], name="fk_review_plan_tasks_day", ondelete="CASCADE"),
    )

    op.create_table(
        "review_progresses",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("day_id", UuidString(), nullable=False),
        sa.Column("task_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("elapsed_minutes", sa.Integer(), nullable=True),
        sa.Column("mastery_score", sa.Integer(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_progresses_plan", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["day_id"], ["review_plan_days.id"], name="fk_review_progresses_day", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["review_plan_tasks.id"], name="fk_review_progresses_task", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", "task_id", name="uq_review_progresses_user_task"),
    )
    op.create_index("ix_review_progresses_plan_done", "review_progresses", ["plan_id", "done"])

    op.create_table(
        "review_intro_scripts",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("script_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("scenario", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_intro_scripts_plan", ondelete="CASCADE"),
    )

    op.create_table(
        "review_star_cards",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("card_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("tag", sa.String(length=128), nullable=False),
        sa.Column("background", sa.Text(), nullable=False),
        sa.Column("challenge", sa.Text(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_star_cards_plan", ondelete="CASCADE"),
    )

    op.create_table(
        "review_a4_memory_items",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_a4_memory_plan", ondelete="CASCADE"),
    )

    op.create_table(
        "practice_questions",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("practice_category", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=64), nullable=True),
        sa.Column("question_type", sa.String(length=64), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("choices_json", JsonDict(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answer_detail", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("tags_json", JsonDict(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "content_hash", name="uq_practice_questions_user_hash"),
    )
    op.create_index("ix_practice_questions_category", "practice_questions", ["tenant_id", "user_id", "practice_category", "subject"])

    op.create_table(
        "practice_wrong_book",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("question_id", UuidString(), nullable=False),
        sa.Column("mark_type", sa.String(length=32), nullable=False),
        sa.Column("mastery_level", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["question_id"], ["practice_questions.id"], name="fk_wrong_book_question", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", "question_id", name="uq_wrong_book_user_question"),
    )


def downgrade() -> None:
    op.drop_table("practice_wrong_book")

    op.drop_index("ix_practice_questions_category", table_name="practice_questions")
    op.drop_table("practice_questions")

    op.drop_table("review_a4_memory_items")
    op.drop_table("review_star_cards")
    op.drop_table("review_intro_scripts")

    op.drop_index("ix_review_progresses_plan_done", table_name="review_progresses")
    op.drop_table("review_progresses")

    op.drop_table("review_plan_tasks")
    op.drop_table("review_plan_days")

    op.drop_index("ix_review_plan_phases_plan", table_name="review_plan_phases")
    op.drop_table("review_plan_phases")

    op.drop_index("ix_review_plans_tenant_updated", table_name="review_plans")
    op.drop_table("review_plans")
