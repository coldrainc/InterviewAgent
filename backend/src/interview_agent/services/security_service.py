from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import (
    AuthRefreshTokenModel,
    SecurityEventModel,
    UserRoleAssignmentModel,
)


ROLE_ORDER = {"user": 10, "support": 20, "admin": 30, "server": 40}
ROLE_PERMISSIONS = {
    "user": {"account:read", "session:write", "practice:write"},
    "support": {"account:read", "security:read", "users:read"},
    "admin": {"account:read", "security:read", "users:read", "users:write", "roles:write"},
    "server": {"account:read", "security:read", "users:read", "users:write", "roles:write", "billing:write"},
}


@dataclass(frozen=True)
class IssuedRefreshToken:
    token: str
    expires_at: datetime
    family_id: str


class SecurityService:
    def __init__(self, session: AsyncSession, *, tenant_id: str = "default") -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def issue_refresh_token(
        self,
        *,
        user_id: str,
        platform: str,
        ttl_seconds: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        family_id: str | None = None,
    ) -> IssuedRefreshToken:
        token = secrets.token_urlsafe(48)
        expires_at = utcnow() + timedelta(seconds=max(ttl_seconds, 3600))
        token_family = family_id or secrets.token_urlsafe(16)
        self.session.add(
            AuthRefreshTokenModel(
                tenant_id=self.tenant_id,
                user_id=user_id,
                token_hash=hash_token(token),
                family_id=token_family,
                platform=clean_platform(platform),
                ip_address=clean_ip(ip_address),
                user_agent=clean_user_agent(user_agent),
                revoked=False,
                created_at=utcnow(),
                expires_at=expires_at,
            )
        )
        await self.session.flush()
        return IssuedRefreshToken(token=token, expires_at=expires_at, family_id=token_family)

    async def rotate_refresh_token(
        self,
        *,
        refresh_token: str,
        ttl_seconds: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[AuthRefreshTokenModel, IssuedRefreshToken]:
        token_hash = hash_token(refresh_token)
        result = await self.session.execute(
            select(AuthRefreshTokenModel).where(
                AuthRefreshTokenModel.tenant_id == self.tenant_id,
                AuthRefreshTokenModel.token_hash == token_hash,
            )
        )
        current = result.scalar_one_or_none()
        if current is None:
            raise ValueError("refresh token not found")
        if current.revoked or current.expires_at <= utcnow():
            await self.revoke_refresh_family(current.family_id)
            raise ValueError("refresh token revoked or expired")
        if current.used_at is not None or current.replaced_by_token_id is not None:
            await self.revoke_refresh_family(current.family_id)
            await self.record_event(
                user_id=current.user_id,
                event_type="refresh_token_reuse_detected",
                severity="critical",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"family_id": current.family_id},
            )
            raise ValueError("refresh token reuse detected")
        replacement = await self.issue_refresh_token(
            user_id=current.user_id,
            platform=current.platform,
            ttl_seconds=ttl_seconds,
            ip_address=ip_address,
            user_agent=user_agent,
            family_id=current.family_id,
        )
        replacement_model = await self._get_refresh_by_hash(hash_token(replacement.token))
        current.used_at = utcnow()
        current.revoked = True
        current.revoked_at = utcnow()
        current.replaced_by_token_id = replacement_model.id if replacement_model else None
        await self.session.flush()
        return current, replacement

    async def revoke_refresh_family(self, family_id: str) -> None:
        await self.session.execute(
            update(AuthRefreshTokenModel)
            .where(AuthRefreshTokenModel.tenant_id == self.tenant_id, AuthRefreshTokenModel.family_id == family_id)
            .values(revoked=True, revoked_at=utcnow())
        )
        await self.session.flush()

    async def revoke_user_refresh_tokens(self, user_id: str) -> int:
        result = await self.session.execute(
            update(AuthRefreshTokenModel)
            .where(
                AuthRefreshTokenModel.tenant_id == self.tenant_id,
                AuthRefreshTokenModel.user_id == user_id,
                AuthRefreshTokenModel.revoked.is_(False),
            )
            .values(revoked=True, revoked_at=utcnow())
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def revoke_refresh_token(self, refresh_token: str, *, user_id: str | None = None) -> int:
        query = (
            update(AuthRefreshTokenModel)
            .where(
                AuthRefreshTokenModel.tenant_id == self.tenant_id,
                AuthRefreshTokenModel.token_hash == hash_token(refresh_token),
                AuthRefreshTokenModel.revoked.is_(False),
            )
            .values(revoked=True, revoked_at=utcnow())
        )
        if user_id:
            query = query.where(AuthRefreshTokenModel.user_id == user_id)
        result = await self.session.execute(query)
        await self.session.flush()
        return int(result.rowcount or 0)

    async def record_event(
        self,
        *,
        event_type: str,
        severity: str = "info",
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        metadata: dict | None = None,
    ) -> SecurityEventModel:
        event = SecurityEventModel(
            tenant_id=self.tenant_id,
            user_id=user_id,
            event_type=event_type,
            severity=clean_severity(severity),
            ip_address=clean_ip(ip_address),
            user_agent=clean_user_agent(user_agent),
            request_id=(request_id or "")[:128] or None,
            metadata_json=metadata or {},
            created_at=utcnow(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def recent_event_count(
        self,
        *,
        event_type: str,
        ip_address: str | None = None,
        user_id: str | None = None,
        minutes: int = 60,
    ) -> int:
        query = select(func.count(SecurityEventModel.id)).where(
            SecurityEventModel.tenant_id == self.tenant_id,
            SecurityEventModel.event_type == event_type,
            SecurityEventModel.created_at >= utcnow() - timedelta(minutes=minutes),
        )
        if ip_address:
            query = query.where(SecurityEventModel.ip_address == clean_ip(ip_address))
        if user_id:
            query = query.where(SecurityEventModel.user_id == user_id)
        value = await self.session.scalar(query)
        return int(value or 0)

    async def list_events(self, *, limit: int = 100) -> list[SecurityEventModel]:
        result = await self.session.execute(
            select(SecurityEventModel)
            .where(SecurityEventModel.tenant_id == self.tenant_id)
            .order_by(SecurityEventModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_role(self, user_id: str) -> str:
        result = await self.session.execute(
            select(UserRoleAssignmentModel.role)
            .where(
                UserRoleAssignmentModel.tenant_id == self.tenant_id,
                UserRoleAssignmentModel.user_id == user_id,
                UserRoleAssignmentModel.revoked_at.is_(None),
            )
        )
        roles = [role for role in result.scalars().all() if role in ROLE_ORDER]
        if not roles:
            return "user"
        return max(roles, key=lambda role: ROLE_ORDER[role])

    async def grant_role(self, *, user_id: str, role: str, granted_by: str, metadata: dict | None = None) -> None:
        cleaned_role = clean_role(role)
        existing = await self.session.execute(
            select(UserRoleAssignmentModel).where(
                UserRoleAssignmentModel.tenant_id == self.tenant_id,
                UserRoleAssignmentModel.user_id == user_id,
                UserRoleAssignmentModel.role == cleaned_role,
            )
        )
        model = existing.scalar_one_or_none()
        if model:
            model.revoked_at = None
            model.granted_by = granted_by
            model.metadata_json = metadata or {}
        else:
            self.session.add(
                UserRoleAssignmentModel(
                    tenant_id=self.tenant_id,
                    user_id=user_id,
                    role=cleaned_role,
                    granted_by=granted_by,
                    metadata_json=metadata or {},
                    created_at=utcnow(),
                )
            )
        await self.record_event(
            user_id=user_id,
            event_type="role_granted",
            severity="warning",
            metadata={"role": cleaned_role, "granted_by": granted_by},
        )
        await self.session.flush()

    async def revoke_role(self, *, user_id: str, role: str, revoked_by: str) -> bool:
        result = await self.session.execute(
            select(UserRoleAssignmentModel).where(
                UserRoleAssignmentModel.tenant_id == self.tenant_id,
                UserRoleAssignmentModel.user_id == user_id,
                UserRoleAssignmentModel.role == clean_role(role),
                UserRoleAssignmentModel.revoked_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.revoked_at = utcnow()
        await self.record_event(
            user_id=user_id,
            event_type="role_revoked",
            severity="warning",
            metadata={"role": model.role, "revoked_by": revoked_by},
        )
        await self.session.flush()
        return True

    async def list_roles(self, *, limit: int = 200) -> list[UserRoleAssignmentModel]:
        result = await self.session.execute(
            select(UserRoleAssignmentModel)
            .where(UserRoleAssignmentModel.tenant_id == self.tenant_id, UserRoleAssignmentModel.revoked_at.is_(None))
            .order_by(UserRoleAssignmentModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_refresh_by_hash(self, token_hash: str) -> AuthRefreshTokenModel | None:
        result = await self.session.execute(
            select(AuthRefreshTokenModel).where(
                AuthRefreshTokenModel.tenant_id == self.tenant_id,
                AuthRefreshTokenModel.token_hash == token_hash,
            )
        )
        return result.scalar_one_or_none()


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(clean_role(role), set())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def security_event_to_dict(event: SecurityEventModel) -> dict:
    return {
        "id": str(event.id),
        "tenant_id": event.tenant_id,
        "user_id": event.user_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "request_id": event.request_id,
        "metadata": event.metadata_json,
        "created_at": event.created_at.isoformat(),
    }


def role_assignment_to_dict(role: UserRoleAssignmentModel) -> dict:
    return {
        "id": str(role.id),
        "tenant_id": role.tenant_id,
        "user_id": role.user_id,
        "role": role.role,
        "granted_by": role.granted_by,
        "metadata": role.metadata_json,
        "created_at": role.created_at.isoformat(),
        "revoked_at": role.revoked_at.isoformat() if role.revoked_at else None,
    }


def clean_role(role: str) -> str:
    cleaned = str(role or "user").strip().lower()
    return cleaned if cleaned in ROLE_ORDER else "user"


def clean_platform(platform: str) -> str:
    cleaned = "".join(char for char in str(platform or "unknown").lower() if char.isalnum() or char in {"_", "-"})
    return cleaned[:32] or "unknown"


def clean_ip(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned[:64] or None


def clean_user_agent(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned[:512] or None


def clean_severity(value: str) -> str:
    cleaned = str(value or "info").strip().lower()
    return cleaned if cleaned in {"info", "warning", "critical"} else "info"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
