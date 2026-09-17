from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260905_0015"
down_revision = "20260905_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "civil_service_questions",
        "id",
        existing_type=sa.String(length=36),
        type_=postgresql.UUID(as_uuid=True),
        postgresql_using="id::uuid",
        existing_nullable=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "civil_service_questions",
        "id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=36),
        postgresql_using="id::text",
        existing_nullable=False,
    )
