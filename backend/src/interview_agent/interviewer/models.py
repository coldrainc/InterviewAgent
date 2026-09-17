from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from interview_agent.infrastructure.db.models import Base, JsonDict, UuidString, utcnow


class InterviewerKitModel(Base):
    __tablename__ = "interviewer_kits"
    __table_args__ = (Index("ix_interviewer_kits_owner_updated", "tenant_id", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    seniority: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    dimensions_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    questions_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class InterviewerEvidenceModel(Base):
    __tablename__ = "interviewer_evidence"
    __table_args__ = (
        Index("ix_interviewer_evidence_kit_created", "kit_id", "created_at"),
        UniqueConstraint("tenant_id", "user_id", "kit_id", "client_key", name="uq_interviewer_evidence_client_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kit_id: Mapped[uuid.UUID] = mapped_column(UuidString(), ForeignKey("interviewer_kits.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UuidString(), ForeignKey("interview_sessions.id", ondelete="SET NULL"))
    client_key: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    signal: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    note: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
