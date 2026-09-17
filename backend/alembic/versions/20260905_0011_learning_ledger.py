from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260905_0011"
down_revision = "20260905_0010"
branch_labels = None
depends_on = None


def _owner_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
    ]


def _timestamps(*, updated: bool = False) -> list[sa.Column]:
    columns = [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]
    if updated:
        columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    return columns


def upgrade() -> None:
    op.create_table(
        "learning_goals",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target_role", sa.String(length=255), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("success_criteria_json", JsonDict(), nullable=False),
        sa.Column("constraints_json", JsonDict(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(updated=True),
    )
    op.create_index("ix_learning_goals_owner_status", "learning_goals", ["tenant_id", "user_id", "status"])

    op.create_table(
        "learning_plan_versions",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("plan_id", UuidString(), sa.ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UuidString(), sa.ForeignKey("learning_goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_json", JsonDict(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "user_id", "plan_id", "version", name="uq_learning_plan_version"),
    )
    op.create_index(
        "ix_learning_plan_versions_plan", "learning_plan_versions", ["tenant_id", "user_id", "plan_id", "version"]
    )

    op.create_table(
        "learning_task_runs",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("plan_id", UuidString(), sa.ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", UuidString(), sa.ForeignKey("review_plan_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("progress_id", UuidString(), sa.ForeignKey("review_progresses.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "plan_version_id", UuidString(), sa.ForeignKey("learning_plan_versions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(updated=True),
        sa.UniqueConstraint("tenant_id", "user_id", "task_id", name="uq_learning_task_runs_owner_task"),
    )
    op.create_index("ix_learning_task_runs_owner_status", "learning_task_runs", ["tenant_id", "user_id", "status"])
    op.create_index("ix_learning_task_runs_plan", "learning_task_runs", ["tenant_id", "user_id", "plan_id"])

    op.create_table(
        "learning_evidence",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("run_id", UuidString(), sa.ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", JsonDict(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_learning_evidence_run_created", "learning_evidence", ["run_id", "created_at"])
    op.create_index(
        "ix_learning_evidence_owner_source",
        "learning_evidence",
        ["tenant_id", "user_id", "source_type", "source_id"],
    )

    op.create_table(
        "learning_verifications",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("run_id", UuidString(), sa.ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_json", JsonDict(), nullable=False),
        sa.Column("verifier", sa.String(length=64), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_learning_verifications_run_created", "learning_verifications", ["run_id", "created_at"])

    op.create_table(
        "learning_effect_receipts",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("run_id", UuidString(), sa.ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", UuidString(), sa.ForeignKey("review_plan_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "verification_id", UuidString(), sa.ForeignKey("learning_verifications.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("receipt_json", JsonDict(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "idempotency_key", name="uq_learning_receipts_owner_idempotency"
        ),
    )
    op.create_index("ix_learning_receipts_run_created", "learning_effect_receipts", ["run_id", "created_at"])
    op.create_index(
        "ix_learning_receipts_task_created",
        "learning_effect_receipts",
        ["tenant_id", "user_id", "task_id", "created_at"],
    )

    op.create_table(
        "learning_plan_revisions",
        sa.Column("id", UuidString(), primary_key=True),
        *_owner_columns(),
        sa.Column("plan_id", UuidString(), sa.ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "from_version_id", UuidString(), sa.ForeignKey("learning_plan_versions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "to_version_id", UuidString(), sa.ForeignKey("learning_plan_versions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("trigger_json", JsonDict(), nullable=False),
        sa.Column("diff_json", JsonDict(), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("reversible", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_learning_revisions_plan_created", "learning_plan_revisions", ["plan_id", "created_at"])


def downgrade() -> None:
    op.drop_table("learning_plan_revisions")
    op.drop_table("learning_effect_receipts")
    op.drop_table("learning_verifications")
    op.drop_table("learning_evidence")
    op.drop_table("learning_task_runs")
    op.drop_table("learning_plan_versions")
    op.drop_table("learning_goals")
