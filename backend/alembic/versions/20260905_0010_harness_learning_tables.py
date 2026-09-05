from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0010"
down_revision = "20260904_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---- 新表：面试结构化报告 ----
    op.create_table(
        "interview_reports",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", UuidString(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("dimension_scores_json", JsonDict(), nullable=False),
        sa.Column("per_question_json", JsonDict(), nullable=False),
        sa.Column("evidence_json", JsonDict(), nullable=False),
        sa.Column("strength_tags_json", JsonDict(), nullable=False),
        sa.Column("weakness_tags_json", JsonDict(), nullable=False),
        sa.Column("suggestions_json", JsonDict(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("report_version", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name="fk_interview_reports_session", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", "session_id", name="uq_interview_reports_user_session"),
    )
    op.create_index("ix_interview_reports_tenant_updated", "interview_reports", ["tenant_id", "user_id", "updated_at"])

    # ---- 新表：刷题作答记录 ----
    op.create_table(
        "practice_attempts",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("question_id", UuidString(), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["question_id"], ["practice_questions.id"], name="fk_practice_attempts_question", ondelete="CASCADE"),
    )
    op.create_index("ix_practice_attempts_tenant_created", "practice_attempts", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_practice_attempts_question", "practice_attempts", ["question_id"])

    # ---- 新表：每日打卡 ----
    op.create_table(
        "review_checkins",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("plan_id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("tasks_done", sa.Integer(), nullable=False),
        sa.Column("total_tasks", sa.Integer(), nullable=False),
        sa.Column("elapsed_minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["review_plans.id"], name="fk_review_checkins_plan", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", "plan_id", "checkin_date", name="uq_review_checkins_user_plan_date"),
    )
    op.create_index("ix_review_checkins_tenant_date", "review_checkins", ["tenant_id", "user_id", "checkin_date"])

    # ---- 新表：用户成就 ----
    op.create_table(
        "user_achievements",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("achievement_key", sa.String(length=64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "achievement_key", name="uq_user_achievements_user_key"),
    )
    op.create_index("ix_user_achievements_tenant", "user_achievements", ["tenant_id", "user_id", "unlocked_at"])

    # ---- 存量表加字段 ----
    op.add_column("review_plans", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("review_plan_days", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("review_plan_tasks", sa.Column("source", sa.String(length=32), nullable=False, server_default="plan"))
    op.add_column("review_plan_tasks", sa.Column("source_ref", sa.String(length=255), nullable=True))
    op.add_column("review_plan_tasks", sa.Column("link_type", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column("review_plan_tasks", sa.Column("link_payload_json", JsonDict(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("review_plan_tasks", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column(
        "interview_sessions",
        sa.Column("plan_task_id", UuidString(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_sessions_plan_task",
        "interview_sessions",
        "review_plan_tasks",
        ["plan_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_review_plan_days_scheduled_date", "review_plan_days", ["scheduled_date"])

    # ---- 存量数据回填：计划开始日期 = 创建日；每日日期按 sort_order 顺排 ----
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE review_plans SET start_date = created_at::date
            WHERE start_date IS NULL
            """
        )
        op.execute(
            """
            UPDATE review_plan_days d
            SET scheduled_date = sub.sdate
            FROM (
                SELECT d2.id,
                       (p.start_date
                        + (ROW_NUMBER() OVER (PARTITION BY d2.plan_id ORDER BY d2.sort_order) - 1)
                        * INTERVAL '1 day')::date AS sdate
                FROM review_plan_days d2
                JOIN review_plans p ON p.id = d2.plan_id
                WHERE p.start_date IS NOT NULL
            ) sub
            WHERE d.id = sub.id AND d.scheduled_date IS NULL
            """
        )


def downgrade() -> None:
    op.drop_index("ix_review_plan_days_scheduled_date", table_name="review_plan_days")
    op.drop_constraint("fk_interview_sessions_plan_task", "interview_sessions", type_="foreignkey")
    op.drop_column("interview_sessions", "plan_task_id")
    op.drop_column("review_plan_tasks", "reason")
    op.drop_column("review_plan_tasks", "link_payload_json")
    op.drop_column("review_plan_tasks", "link_type")
    op.drop_column("review_plan_tasks", "source_ref")
    op.drop_column("review_plan_tasks", "source")
    op.drop_column("review_plan_days", "scheduled_date")
    op.drop_column("review_plans", "start_date")

    op.drop_index("ix_user_achievements_tenant", table_name="user_achievements")
    op.drop_table("user_achievements")

    op.drop_index("ix_review_checkins_tenant_date", table_name="review_checkins")
    op.drop_table("review_checkins")

    op.drop_index("ix_practice_attempts_question", table_name="practice_attempts")
    op.drop_index("ix_practice_attempts_tenant_created", table_name="practice_attempts")
    op.drop_table("practice_attempts")

    op.drop_index("ix_interview_reports_tenant_updated", table_name="interview_reports")
    op.drop_table("interview_reports")
