from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from interview_agent.infrastructure.db.models import Base, JsonDict, UuidString, utcnow


class TrainingDrillModel(Base):
    __tablename__ = "training_drills"
    __table_args__ = (Index("ix_training_drills_owner_created", "tenant_id", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    focus: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="question_bank")
    question_ids_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpacedReviewItemModel(Base):
    __tablename__ = "spaced_review_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "question_id", name="uq_spaced_review_owner_question"),
        Index("ix_spaced_review_owner_due", "tenant_id", "user_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UuidString(), ForeignKey("practice_questions.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="learning")
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ease_score: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
