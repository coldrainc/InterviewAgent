from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from fastapi import Header, HTTPException, Request, status
from sqlalchemy import select

from interview_agent.infrastructure.settings import AppSettings, load_settings


TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
CLIENT_PLATFORMS = frozenset({"web", "desktop", "android", "ios", "harmony", "miniapp"})


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    authenticated: bool
    user_id: str = "anonymous"
    platform: str = "unknown"
    role: str = "user"
    request_id: str | None = None
    client_platform: str = "unknown"
    client_version: str = "unknown"
    client_request_id: str | None = None
    platform_matched: bool | None = None


@dataclass(frozen=True)
class ClientRequestMetadata:
    platform: str = "unknown"
    version: str = "unknown"
    request_id: str | None = None


def client_request_metadata(request: Request) -> ClientRequestMetadata:
    request_id = clean_request_id(
        request.headers.get("X-Client-Request-Id") or request.headers.get("X-Request-ID")
    )
    return ClientRequestMetadata(
        platform=clean_client_platform(request.headers.get("X-Client-Platform")),
        version=clean_client_version(request.headers.get("X-Client-Version")),
        request_id=request_id,
    )


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def check(self, key: str, limit: int, now: float | None = None) -> bool:
        if limit <= 0:
            return True
        timestamp = int(now or time.time())
        window = timestamp // 60
        with self._lock:
            current_window, count = self._windows.get(key, (window, 0))
            if current_window != window:
                self._windows[key] = (window, 1)
                return True
            if count >= limit:
                return False
            self._windows[key] = (window, count + 1)
            return True


rate_limiter = FixedWindowRateLimiter()


def parse_api_tokens(value: str) -> dict[str, tuple[str, str]]:
    tokens: dict[str, tuple[str, str]] = {}
    for item in value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        if ":" in stripped:
            token, tenant_id, *role_parts = stripped.split(":")
        else:
            token, tenant_id, role_parts = stripped, "default", []
        token = token.strip()
        tenant_id = tenant_id.strip()
        role = role_parts[0].strip() if role_parts else "server"
        if token and _valid_tenant_id(tenant_id):
            tokens[token] = (tenant_id, _clean_role(role))
    return tokens


async def request_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> RequestContext:
    settings = load_settings()
    client = client_request_metadata(request)
    context = authenticate_request(settings, authorization=authorization, x_api_key=x_api_key)
    request_id = (
        getattr(request.state, "request_id", None)
        or clean_request_id(x_request_id)
        or client.request_id
    )
    context = RequestContext(
        tenant_id=context.tenant_id,
        authenticated=context.authenticated,
        user_id=context.user_id,
        platform=context.platform,
        role=context.role,
        request_id=request_id,
        client_platform=client.platform,
        client_version=client.version,
        client_request_id=client.request_id,
        platform_matched=_platforms_match(context, client),
    )
    client_host = request.client.host if request.client else "unknown"
    limit_key = f"{context.tenant_id}:{client_host}"
    if not rate_limiter.check(limit_key, settings.rate_limit_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试。",
        )
    if context.authenticated and context.platform != "server":
        from interview_agent.infrastructure.db.models import UserAccountModel, UserRoleAssignmentModel
        from interview_agent.infrastructure.db.session import session_scope

        async with session_scope() as db:
            account_row = (
                await db.execute(
                    select(UserAccountModel.status, UserAccountModel.id).where(
                        UserAccountModel.tenant_id == context.tenant_id,
                        UserAccountModel.user_id == context.user_id,
                    )
                )
            ).one_or_none()
            account_status = account_row[0] if account_row else None
            active_roles = list(
                (
                    await db.execute(
                        select(UserRoleAssignmentModel.role).where(
                            UserRoleAssignmentModel.tenant_id == context.tenant_id,
                            UserRoleAssignmentModel.user_id == context.user_id,
                            UserRoleAssignmentModel.revoked_at.is_(None),
                        )
                    )
                ).scalars().all()
            )
        if account_status is not None:
            role_order = {"user": 10, "support": 20, "admin": 30}
            resolved_role = max(active_roles, key=lambda item: role_order.get(item, 0), default="user")
            context = RequestContext(
                tenant_id=context.tenant_id,
                authenticated=context.authenticated,
                user_id=context.user_id,
                platform=context.platform,
                role=resolved_role,
                request_id=context.request_id,
                client_platform=context.client_platform,
                client_version=context.client_version,
                client_request_id=context.client_request_id,
                platform_matched=context.platform_matched,
            )
        if account_status in {"deleted", "suspended"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=("账号已删除。" if account_status == "deleted" else "账号当前不可用，请联系管理员。"),
                headers={"WWW-Authenticate": "Bearer"},
            )
    request.state.request_context = context
    return context


def authenticate_request(
    settings: AppSettings,
    *,
    authorization: str | None,
    x_api_key: str | None,
) -> RequestContext:
    configured_tokens = parse_api_tokens(settings.api_tokens)
    admin_tokens = parse_api_tokens(settings.admin_api_tokens)
    token = _extract_bearer_token(authorization) or (x_api_key.strip() if x_api_key else None)
    if token and token in admin_tokens:
        tenant_id, role = admin_tokens[token]
        return RequestContext(
            tenant_id=tenant_id,
            authenticated=True,
            user_id="admin-token",
            platform="server",
            role=role if role == "admin" else "admin",
        )
    if token and token in configured_tokens:
        tenant_id, role = configured_tokens[token]
        return RequestContext(
            tenant_id=tenant_id,
            authenticated=True,
            user_id="api-token",
            platform="server",
            role=role,
        )
    if token:
        signed_context = verify_client_token(settings, token)
        if signed_context:
            return signed_context
    if settings.api_auth_required:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的 API Token。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tenant_id = settings.default_tenant_id if _valid_tenant_id(settings.default_tenant_id) else "default"
    return RequestContext(tenant_id=tenant_id, authenticated=False)


def validate_production_security(settings: AppSettings) -> None:
    if not settings.is_production:
        return
    problems: list[str] = []
    if not settings.api_auth_required:
        problems.append("INTERVIEW_API_AUTH_REQUIRED 必须为 true")
    if settings.auth_token_secret == "dev-secret-change-me" or len(settings.auth_token_secret) < 32:
        problems.append("INTERVIEW_AUTH_TOKEN_SECRET 必须替换为至少 32 字符的强随机密钥")
    if settings.auth_dev_login_enabled:
        problems.append("INTERVIEW_AUTH_DEV_LOGIN_ENABLED 必须为 false")
    if settings.auth_mock_provider_login_enabled:
        problems.append("INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED 必须为 false")
    if settings.allow_mock_recharge:
        problems.append("INTERVIEW_ALLOW_MOCK_RECHARGE 必须为 false")
    if not settings.payment_webhook_secret or len(settings.payment_webhook_secret) < 24:
        problems.append("INTERVIEW_PAYMENT_WEBHOOK_SECRET 必须配置为至少 24 字符")
    if settings.object_storage_backend == "local":
        problems.append("INTERVIEW_OBJECT_STORAGE_BACKEND 生产环境不能使用 local")
    if settings.database_url.startswith("sqlite"):
        problems.append("DATABASE_URL 生产环境不能使用 SQLite")
    if "*" in [item.strip() for item in settings.allowed_origins.split(",")]:
        problems.append("INTERVIEW_ALLOWED_ORIGINS 生产环境不能使用 *")
    if problems:
        raise RuntimeError("生产安全配置未通过：" + "；".join(problems))


def issue_client_token(
    settings: AppSettings,
    *,
    tenant_id: str,
    user_id: str,
    platform: str,
    display_name: str = "",
    role: str = "user",
    now: float | None = None,
) -> tuple[str, int]:
    if not _valid_tenant_id(tenant_id):
        raise ValueError("invalid tenant_id")
    if not _valid_subject_id(user_id):
        raise ValueError("invalid user_id")
    issued_at = int(now or time.time())
    expires_at = issued_at + max(settings.auth_token_ttl_seconds, 60)
    payload = {
        "typ": "interview-agent-client",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "platform": _clean_platform(platform),
        "role": _clean_role(role),
        "jti": secrets.token_urlsafe(16),
        "display_name": display_name[:80],
        "iat": issued_at,
        "exp": expires_at,
    }
    encoded_payload = _b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(settings.auth_token_secret, encoded_payload)
    return f"{encoded_payload}.{signature}", expires_at


def verify_client_token(settings: AppSettings, token: str, now: float | None = None) -> RequestContext | None:
    payload_part, separator, signature = token.partition(".")
    if not separator or not payload_part or not signature:
        return None
    expected_signature = _sign(settings.auth_token_secret, payload_part)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        payload = json.loads(_b64decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("typ") != "interview-agent-client":
        return None
    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(now or time.time()):
        return None
    tenant_id = str(payload.get("tenant_id", ""))
    user_id = str(payload.get("user_id", ""))
    if not _valid_tenant_id(tenant_id) or not _valid_subject_id(user_id):
        return None
    return RequestContext(
        tenant_id=tenant_id,
        authenticated=True,
        user_id=user_id,
        platform=_clean_platform(str(payload.get("platform", "unknown"))),
        role=_clean_role(str(payload.get("role", "user"))),
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _valid_tenant_id(value: str) -> bool:
    return bool(TENANT_PATTERN.fullmatch(value))


def _valid_subject_id(value: str) -> bool:
    return bool(re.fullmatch(r"^[a-zA-Z0-9][a-zA-Z0-9_:@.+\-]{0,127}$", value))


def _clean_platform(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", value.strip().lower())
    return cleaned[:32] or "unknown"


def _clean_role(value: str) -> str:
    cleaned = value.strip().lower()
    return cleaned if cleaned in {"user", "support", "server", "admin"} else "user"


def clean_request_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9_.:@-]", "", value.strip())
    return cleaned[:128] or None


def clean_client_platform(value: str | None) -> str:
    if not value:
        return "unknown"
    cleaned = _clean_platform(value)
    return cleaned if cleaned in CLIENT_PLATFORMS else "unknown"


def clean_client_version(value: str | None) -> str:
    if not value:
        return "unknown"
    cleaned = value.strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.+\-]{0,63}", cleaned):
        return "unknown"
    return cleaned


def _platforms_match(context: RequestContext, client: ClientRequestMetadata) -> bool | None:
    if not context.authenticated or context.platform == "server" or client.platform == "unknown":
        return None
    return context.platform == client.platform


_clean_request_id = clean_request_id


def _sign(secret: str, payload_part: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
