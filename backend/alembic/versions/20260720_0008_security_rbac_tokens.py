from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from interview_agent.infrastructure.db.models import JsonDict, UuidString


revision = "20260720_0008"
down_revision = "20260720_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("replaced_by_token_id", UuidString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_hash"),
    )
    op.create_index("ix_auth_refresh_tokens_tenant_user_created", "auth_refresh_tokens", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_auth_refresh_tokens_family", "auth_refresh_tokens", ["family_id"])

    op.create_table(
        "security_events",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_tenant_created", "security_events", ["tenant_id", "created_at"])
    op.create_index("ix_security_events_tenant_user_created", "security_events", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_security_events_ip_created", "security_events", ["ip_address", "created_at"])
    op.create_index("ix_security_events_type_created", "security_events", ["event_type", "created_at"])

    op.create_table(
        "user_role_assignments",
        sa.Column("id", UuidString(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("granted_by", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JsonDict(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "role", name="uq_user_role_assignments_active_role"),
    )
    op.create_index("ix_user_role_assignments_tenant_user", "user_role_assignments", ["tenant_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_role_assignments_tenant_user", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")
    op.drop_index("ix_security_events_type_created", table_name="security_events")
    op.drop_index("ix_security_events_ip_created", table_name="security_events")
    op.drop_index("ix_security_events_tenant_user_created", table_name="security_events")
    op.drop_index("ix_security_events_tenant_created", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_auth_refresh_tokens_family", table_name="auth_refresh_tokens")
    op.drop_index("ix_auth_refresh_tokens_tenant_user_created", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
