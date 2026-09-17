from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from interview_agent.infrastructure.db.models import Base, JsonDict, UuidString, utcnow


class DataDeletionRequestModel(Base):
    __tablename__ = "data_deletion_requests"
    __table_args__ = (
        Index("ix_data_deletion_owner_status", "tenant_id", "user_id", "status"),
        Index("ix_data_deletion_status_execute", "status", "execute_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UuidString(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    reason: Mapped[str | None] = mapped_column(Text)
    scope_json: Mapped[dict] = mapped_column(JsonDict(), nullable=False, default=dict)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    execute_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
