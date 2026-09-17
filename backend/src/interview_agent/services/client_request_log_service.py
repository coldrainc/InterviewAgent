from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request

from interview_agent.infrastructure.db.models import ClientRequestLogModel, SecurityEventModel, utcnow
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import (
    RequestContext,
    authenticate_request,
    client_request_metadata,
)
from interview_agent.infrastructure.settings import AppSettings


logger = logging.getLogger("interview_agent.client_requests")


def resolve_audit_context(request: Request, settings: AppSettings) -> RequestContext:
    existing = getattr(request.state, "request_context", None)
    if isinstance(existing, RequestContext):
        return existing
    try:
        return authenticate_request(
            settings,
            authorization=request.headers.get("Authorization"),
            x_api_key=request.headers.get("X-API-Key"),
        )
    except HTTPException:
        return RequestContext(tenant_id=settings.default_tenant_id, authenticated=False)


def route_path(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    value = template if isinstance(template, str) and template else request.url.path
    return value[:255]


async def record_client_request(
    request: Request,
    *,
    settings: AppSettings,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> None:
    client = client_request_metadata(request)
    context = resolve_audit_context(request, settings)
    platform_matched = (
        context.platform == client.platform
        if context.authenticated and context.platform != "server" and client.platform != "unknown"
        else None
    )
    async with session_scope() as session:
        session.add(
            ClientRequestLogModel(
                tenant_id=context.tenant_id,
                user_id=context.user_id if context.authenticated else None,
                auth_platform=context.platform if context.authenticated else "unknown",
                client_platform=client.platform,
                client_version=client.version,
                request_id=request_id,
                method=request.method[:16],
                path=route_path(request),
                status_code=status_code,
                duration_ms=max(0, round(duration_ms)),
                platform_matched=platform_matched,
                created_at=utcnow(),
            )
        )
        if platform_matched is False:
            session.add(
                SecurityEventModel(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    event_type="platform_mismatch",
                    severity="warning",
                    request_id=request_id,
                    metadata_json={
                        "auth_platform": context.platform,
                        "client_platform": client.platform,
                        "client_version": client.version,
                        "path": route_path(request),
                    },
                    created_at=utcnow(),
                )
            )


async def record_client_request_safely(**kwargs: Any) -> None:
    try:
        await record_client_request(**kwargs)
    except Exception:
        logger.exception(
            "client_request_log_failed",
            extra={"request_id": kwargs.get("request_id")},
        )
