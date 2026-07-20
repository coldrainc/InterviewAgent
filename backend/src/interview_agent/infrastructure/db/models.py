from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator


class JsonDict(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UuidString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return parsed
        return str(parsed)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserAccountModel(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_accounts_tenant_user"),
        UniqueConstraint("tenant_id", "email", name="uq_user_accounts_tenant_email"),
        Index("ix_user_accounts_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    trial_uses_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    credit_balance_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    credit_ledger: Mapped[list["CreditLedgerModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["UsageRecordModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class CreditLedgerModel(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        Index("ix_credit_ledger_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_credit_ledger_external_order", "external_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="CREDIT")
    external_order_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    account: Mapped[UserAccountModel] = relationship(back_populates="credit_ledger")


class RechargeOrderModel(Base):
    __tablename__ = "recharge_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_order_id", name="uq_recharge_orders_external"),
        Index("ix_recharge_orders_tenant_user_created", "tenant_id", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")
    payment_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    external_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class UsageRecordModel(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_usage_records_session", "session_id"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_usage_records_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_credits_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    trial_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    account: Mapped[UserAccountModel] = relationship(back_populates="usage_records")


class ResumeModel(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "content_hash", name="uq_resumes_tenant_user_content_hash"),
        Index("ix_resumes_tenant_user_updated", "tenant_id", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    object_bucket: Mapped[str | None] = mapped_column(String(255))
    object_key: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list["InterviewSessionModel"]] = relationship(back_populates="resume")


class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        Index("ix_interview_sessions_tenant_user_updated", "tenant_id", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidString(), ForeignKey("resumes.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    seniority: Mapped[str] = mapped_column(String(128), nullable=False)
    config_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    state_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    resume: Mapped[ResumeModel | None] = relationship(back_populates="sessions")
    turns: Mapped[list["InterviewTurnModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class InterviewTurnModel(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_interview_turns_session_index"),
        Index("ix_interview_turns_session_index", "session_id", "turn_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    interviewer: Mapped[str] = mapped_column(Text, nullable=False)
    candidate: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    guardrails_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    session: Mapped[InterviewSessionModel] = relationship(back_populates="turns")
    memory_items: Mapped[list["MemoryItemModel"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )


class MemoryItemModel(Base):
    __tablename__ = "memory_items"
    __table_args__ = (
        Index("ix_memory_items_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_memory_items_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    session_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("interview_turns.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="interview_qa")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    vector_point_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    turn: Mapped[InterviewTurnModel] = relationship(back_populates="memory_items")


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_uri", "content_hash", name="uq_knowledge_doc_source_hash"),
        Index("ix_knowledge_documents_tenant_updated", "tenant_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    chunks: Mapped[list["RagChunkModel"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class RagChunkModel(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunks_document_index"),
        Index("ix_rag_chunks_tenant_doc", "tenant_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    document_id: Mapped[uuid.UUID] = mapped_column(
        UuidString(), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    vector_collection: Mapped[str | None] = mapped_column(String(255))
    vector_point_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    document: Mapped[KnowledgeDocumentModel] = relationship(back_populates="chunks")


class CivilServiceQuestionModel(Base):
    __tablename__ = "civil_service_questions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "content_hash", name="uq_civil_service_questions_user_hash"),
        Index("ix_civil_service_questions_year_subject", "tenant_id", "user_id", "exam_year", "subject"),
        Index("ix_civil_service_questions_type", "tenant_id", "user_id", "question_type"),
        Index("ix_civil_service_questions_updated", "tenant_id", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(Text)
    exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    choices_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    tags_json: Mapped[list] = mapped_column(JsonDict(), nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
