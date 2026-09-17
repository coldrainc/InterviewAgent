from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from interview_agent.infrastructure.db.models import Base, JsonDict, UuidString, utcnow


class LearningGoalModel(Base):
    __tablename__ = "learning_goals"
    __table_args__ = (
        Index("ix_learning_goals_owner_status", "tenant_id", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    deadline: Mapped[date | None] = mapped_column(Date)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    success_criteria_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    constraints_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class LearningPlanVersionModel(Base):
    __tablename__ = "learning_plan_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "plan_id", "version", name="uq_learning_plan_version"),
        Index("ix_learning_plan_versions_plan", "tenant_id", "user_id", "plan_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_goals.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    snapshot_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LearningAbilitySnapshotModel(Base):
    __tablename__ = "learning_ability_snapshots"
    __table_args__ = (
        Index("ix_learning_ability_owner_created", "tenant_id", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_goals.id", ondelete="SET NULL")
    )
    dimensions_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    evidence_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="computed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LearningTaskRunModel(Base):
    __tablename__ = "learning_task_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "task_id", name="uq_learning_task_runs_owner_task"),
        Index("ix_learning_task_runs_owner_status", "tenant_id", "user_id", "status"),
        Index("ix_learning_task_runs_plan", "tenant_id", "user_id", "plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_plan_tasks.id", ondelete="CASCADE"), nullable=False
    )
    progress_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_progresses.id", ondelete="CASCADE"), nullable=False
    )
    plan_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_plan_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="todo")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class LearningEvidenceModel(Base):
    __tablename__ = "learning_evidence"
    __table_args__ = (
        Index("ix_learning_evidence_run_created", "run_id", "created_at"),
        Index("ix_learning_evidence_owner_source", "tenant_id", "user_id", "source_type", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    source_id: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LearningVerificationModel(Base):
    __tablename__ = "learning_verifications"
    __table_args__ = (Index("ix_learning_verifications_run_created", "run_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    verifier: Mapped[str] = mapped_column(String(64), nullable=False, default="learning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LearningEffectReceiptModel(Base):
    __tablename__ = "learning_effect_receipts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "idempotency_key", name="uq_learning_receipts_owner_idempotency"
        ),
        Index("ix_learning_receipts_run_created", "run_id", "created_at"),
        Index("ix_learning_receipts_task_created", "tenant_id", "user_id", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("learning_task_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_plan_tasks.id", ondelete="CASCADE"), nullable=False
    )
    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_verifications.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    receipt_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LearningPlanRevisionModel(Base):
    __tablename__ = "learning_plan_revisions"
    __table_args__ = (Index("ix_learning_revisions_plan_created", "plan_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False
    )
    from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_plan_versions.id", ondelete="SET NULL")
    )
    to_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("learning_plan_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trigger_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    diff_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
