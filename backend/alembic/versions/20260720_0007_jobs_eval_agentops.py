from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260720_0007"
down_revision = "20260720_0006"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", JsonDict(), nullable=False),
        sa.Column("result_json", JsonDict(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_tenant_user_updated", "jobs", ["tenant_id", "user_id", "updated_at"])
    op.create_index("ix_jobs_tenant_status", "jobs", ["tenant_id", "status", "updated_at"])

    op.create_table(
        "job_steps",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("job_id", UuidString(), nullable=False),
        sa.Column("step_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", JsonDict(), nullable=False),
        sa.Column("output_json", JsonDict(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "step_key", name="uq_job_steps_job_key"),
    )
    op.create_index("ix_job_steps_job_created", "job_steps", ["job_id", "created_at"])

    op.create_table(
        "job_events",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("job_id", UuidString(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_events_job_created", "job_events", ["job_id", "created_at"])
    op.create_index("ix_job_events_type_created", "job_events", ["event_type", "created_at"])

    op.create_table(
        "eval_datasets",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_datasets_tenant_user_updated", "eval_datasets", ["tenant_id", "user_id", "updated_at"])

    op.create_table(
        "eval_cases",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("dataset_id", UuidString(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_cases_dataset_created", "eval_cases", ["dataset_id", "created_at"])

    op.create_table(
        "eval_runs",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_id", UuidString(), nullable=True),
        sa.Column("job_id", UuidString(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_runs_tenant_user_created", "eval_runs", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_eval_runs_status_created", "eval_runs", ["status", "created_at"])

    op.create_table(
        "eval_results",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("run_id", UuidString(), nullable=False),
        sa.Column("case_id", UuidString(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["eval_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_results_run_created", "eval_results", ["run_id", "created_at"])

    op.create_table(
        "agent_traces",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", UuidString(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("trace_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", JsonDict(), nullable=False),
        sa.Column("result_json", JsonDict(), nullable=False),
        sa.Column("metrics_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_traces_tenant_user_created", "agent_traces", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_agent_traces_job", "agent_traces", ["job_id"])
    op.create_index("ix_agent_traces_session", "agent_traces", ["session_id"])

    op.create_table(
        "agent_spans",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("trace_id", UuidString(), nullable=False),
        sa.Column("parent_span_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("span_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", JsonDict(), nullable=False),
        sa.Column("output_json", JsonDict(), nullable=False),
        sa.Column("metrics_json", JsonDict(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trace_id"], ["agent_traces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_spans_trace_started", "agent_spans", ["trace_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_spans_trace_started", table_name="agent_spans")
    op.drop_table("agent_spans")
    op.drop_index("ix_agent_traces_session", table_name="agent_traces")
    op.drop_index("ix_agent_traces_job", table_name="agent_traces")
    op.drop_index("ix_agent_traces_tenant_user_created", table_name="agent_traces")
    op.drop_table("agent_traces")
    op.drop_index("ix_eval_results_run_created", table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_index("ix_eval_runs_status_created", table_name="eval_runs")
    op.drop_index("ix_eval_runs_tenant_user_created", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("ix_eval_cases_dataset_created", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index("ix_eval_datasets_tenant_user_updated", table_name="eval_datasets")
    op.drop_table("eval_datasets")
    op.drop_index("ix_job_events_type_created", table_name="job_events")
    op.drop_index("ix_job_events_job_created", table_name="job_events")
    op.drop_table("job_events")
    op.drop_index("ix_job_steps_job_created", table_name="job_steps")
    op.drop_table("job_steps")
    op.drop_index("ix_jobs_tenant_status", table_name="jobs")
    op.drop_index("ix_jobs_tenant_user_updated", table_name="jobs")
    op.drop_table("jobs")
