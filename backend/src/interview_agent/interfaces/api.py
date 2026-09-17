from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from queue import Empty, Queue
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from interview_agent.core.agent_loop import AgentLoop
from interview_agent.core.state import InterviewState
from interview_agent.interfaces.cli import (
    default_vector_path,
    load_config,
    load_embedding_client_for_existing_vectors,
    load_knowledge_base,
    load_vector_store_for_run,
)
from interview_agent.core.config import CandidateProfile, InterviewConfig, InterviewMode, InterviewStage
from interview_agent.core.industry import Industry
from interview_agent.core.prompt_policy import dashboard_advice_system_prompt
from interview_agent.domain.billing import DEFAULT_CHAT_MODEL, micros_to_credits
from interview_agent.infrastructure.auth_providers import AuthProviderError, exchange_wechat_code
from interview_agent.infrastructure.content_security import scan_upload_content
from interview_agent.infrastructure.codex_config import load_codex_model_config
from interview_agent.infrastructure.db.session import (
    configure_database_for_tests,
    init_database,
    session_scope,
)
from interview_agent.infrastructure.model_runtime import (
    is_openai_compatible_provider,
    is_supported_native_provider,
    resolve_model_runtime,
)
from interview_agent.infrastructure.object_storage import ObjectStorage, create_object_storage
from interview_agent.infrastructure.payments import (
    PaymentProviderError,
    create_alipay_page_pay,
    create_wechat_native_pay,
    decrypt_wechat_resource,
    verify_alipay_notify,
    verify_wechat_notify,
)
from interview_agent.infrastructure.resume_parser import ResumeParseError, parse_resume_base64
from interview_agent.domain.resume import StoredResume, stored_resume_to_payload
from interview_agent.infrastructure.security import (
    RequestContext,
    clean_request_id,
    issue_client_token,
    rate_limiter,
    request_context,
    validate_production_security,
)
from interview_agent.services.client_request_log_service import record_client_request_safely
from interview_agent.infrastructure.settings import load_settings
from interview_agent.infrastructure.web_search import WebSearchClient
from interview_agent.interfaces.error_codes import (
    ApiErrorCode,
    error_code_for_detail,
    error_code_for_status,
)
from interview_agent.services.billing_service import (
    BillingError,
    BillingService,
    InsufficientCreditsError,
    list_model_catalog,
    validate_recharge_amount,
)
from interview_agent.services.interview_persistence_service import InterviewPersistenceService
from interview_agent.services.interview_report_service import InterviewReportService
from interview_agent.services.plan_generator_service import PlanGeneratorService
from interview_agent.services.resume_service import ResumeService
from interview_agent.services.subjective_grader import LlmSubjectiveGrader
from interview_agent.services.security_service import (
    SecurityService,
    has_permission,
    role_assignment_to_dict,
    security_event_to_dict,
)
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.achievement_service import safe_evaluate
from interview_agent.services.admin_test_data_service import AdminTestDataService
from interview_agent.admin import create_admin_router
from interview_agent.admin.service import AdminConsoleService
from interview_agent.learning.routes import create_learning_router
from interview_agent.interviewer.routes import router as interviewer_router
from interview_agent.interviewer.service import InterviewerWorkspaceService
from interview_agent.training.routes import router as training_router
from interview_agent.privacy.routes import create_privacy_router
from interview_agent.privacy.worker import run_deletion_worker
from interview_agent.interfaces.routes.catalog import create_catalog_router
from interview_agent.interfaces.routes.operations import create_operations_router
from interview_agent.interfaces.routes.review_plans import create_review_plans_router
from interview_agent.interfaces.routes.review_progress import create_review_progress_router
from interview_agent.interfaces.routes.review_materials import create_review_materials_router
from interview_agent.interfaces.routes.review_practice import create_review_practice_router
from interview_agent.interfaces.routes.study_dashboard import create_study_dashboard_router
from interview_agent.interfaces.schemas import (
    AccountResponse,
    AuthTokenResponse,
    ChatResponse,
    CreatePaymentOrderRequest,
    DeleteResponse,
    DevLoginRequest,
    LogoutRequest,
    MeResponse,
    MessageRequest,
    PasswordLoginRequest,
    PaymentOrderResponse,
    PaymentWebhookPayload,
    PaymentWebhookResponse,
    PhoneLoginRequest,
    PlanGenerateRequest,
    PlanGenerateResponse,
    ProviderLoginRequest,
    RechargeRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResumeImportRequest,
    ResumeParseRequest,
    ResumeParseResponse,
    ResumeRecordResponse,
    RoleGrantRequest,
    RoleRevokeRequest,
    SessionDetailResponse,
    SessionRequest,
    SessionRewindRequest,
    SessionSummaryResponse,
    UpdateUserSettingsRequest,
    UsageResponse,
    UserSettingsResponse,
)

@dataclass
class ApiSession:
    loop: AgentLoop
    config: InterviewConfig
    tenant_id: str
    user_id: str
    model_id: str
    offline: bool = False
    web_search_enabled: bool = False
    resume_id: str | None = None
    plan_task_id: str | None = None
    interviewer_kit_id: str | None = None


sessions: dict[str, ApiSession] = {}
logger = logging.getLogger("interview_agent.api")


def _request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing
    request_id = clean_request_id(
        request.headers.get("X-Client-Request-Id") or request.headers.get("X-Request-ID")
    ) or str(uuid4())
    request.state.request_id = request_id
    return request_id


def _api_success(data, *, request_id: str) -> dict:
    return {
        "code": 0,
        "message": "ok",
        "data": data,
        "request_id": request_id,
    }


def _api_error(
    *,
    status_code: int,
    message: str,
    request_id: str,
    error: ApiErrorCode | str | None = None,
    details: dict | list | None = None,
) -> dict:
    code = error or error_code_for_status(status_code)
    code_value = code.value if isinstance(code, ApiErrorCode) else str(code)
    return {
        "code": status_code,
        "error": code_value,
        "message": message,
        "data": None,
        "request_id": request_id,
        "details": details,
    }


def _public_error_message(status_code: int, detail) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if status_code == 401:
        return "请先登录后再继续。"
    if status_code == 403:
        return "当前账号无权执行该操作。"
    if status_code == 404:
        return "请求的资源不存在。"
    if status_code == 413:
        return "请求内容过大。"
    if status_code == 422:
        return "请求参数格式不正确。"
    if status_code >= 500:
        return "服务暂时不可用，请稍后重试。"
    return "请求处理失败。"


def _is_api_envelope(payload) -> bool:
    return (
        isinstance(payload, dict)
        and "code" in payload
        and "message" in payload
        and "data" in payload
    )


def _should_wrap_json(request: Request, response) -> bool:
    if request.url.path in {"/openapi.json"} or request.url.path.startswith(("/docs", "/redoc")):
        return False
    if request.url.path in {"/payments/alipay/notify", "/payments/wechat/notify"}:
        return False
    if response.status_code == 204:
        return False
    content_type = response.headers.get("content-type", "")
    return "application/json" in content_type


async def _wrap_json_response(request: Request, response):
    if not _should_wrap_json(request, response):
        return response
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    try:
        payload = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    if _is_api_envelope(payload):
        content = payload
    elif response.status_code < 400:
        content = _api_success(payload, request_id=_request_id(request))
    else:
        content = _api_error(
            status_code=response.status_code,
            message=_public_error_message(response.status_code, payload.get("detail") if isinstance(payload, dict) else None),
            request_id=_request_id(request),
            error=error_code_for_detail(
                response.status_code,
                payload.get("detail") if isinstance(payload, dict) else None,
            ),
        )
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"content-length", "content-type"}
    }
    return JSONResponse(content=content, status_code=response.status_code, headers=headers)


def create_app(
    *,
    object_storage: ObjectStorage | None = None,
    initialize_database: bool = True,
    database_engine: AsyncEngine | None = None,
    start_background_workers: bool | None = None,
) -> FastAPI:
    settings = load_settings()
    validate_production_security(settings)
    storage = object_storage or create_object_storage(settings)
    if database_engine is not None:
        configure_database_for_tests(database_engine)
    workers_enabled = database_engine is None if start_background_workers is None else start_background_workers

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if initialize_database:
            await init_database()
        await asyncio.to_thread(storage.ensure_ready)
        deletion_worker = asyncio.create_task(run_deletion_worker(storage)) if workers_enabled else None
        try:
            yield
        finally:
            if deletion_worker is not None:
                deletion_worker.cancel()
                try:
                    await deletion_worker
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title="Interview Agent API", lifespan=lifespan)
    app.include_router(create_learning_router())
    app.include_router(interviewer_router)
    app.include_router(training_router)
    app.include_router(create_privacy_router(object_storage=storage))
    app.include_router(create_catalog_router(settings=settings))
    app.include_router(create_operations_router())
    app.include_router(create_review_plans_router())
    app.include_router(create_review_progress_router())
    app.include_router(create_review_materials_router())
    app.include_router(create_review_practice_router(
        build_subjective_grader=_build_subjective_grader,
        billing_service_factory=_billing_service,
    ))
    app.include_router(create_study_dashboard_router(
        build_advice_provider=_build_dashboard_advice_provider,
        billing_service_factory=_billing_service,
    ))
    app.include_router(create_admin_router())
    allowed_origins = [item.strip() for item in settings.allowed_origins.split(",") if item.strip()]

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request_id = _request_id(request)
        started = time.perf_counter()
        response = await call_next(request)
        if settings.is_production:
            response = await _wrap_json_response(request, response)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        _log_access(request, response.status_code, duration_ms, request_id)
        await record_client_request_safely(
            request=request,
            settings=settings,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=_api_error(
                status_code=exc.status_code,
                message=_public_error_message(exc.status_code, exc.detail),
                request_id=request_id,
                error=error_code_for_detail(exc.status_code, exc.detail),
                details=exc.detail if isinstance(exc.detail, (dict, list)) else None,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=422,
            content=_api_error(
                status_code=422,
                error=ApiErrorCode.VALIDATION_ERROR,
                message="请求参数格式不正确。",
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception(
            "unhandled_api_error",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=500,
            content=_api_error(
                status_code=500,
                error=ApiErrorCode.INTERNAL_SERVER_ERROR,
                message="服务暂时不可用，请稍后重试。",
                request_id=request_id,
            ),
        )

    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Request-ID",
                "X-Client-Platform",
                "X-Client-Version",
                "X-Client-Request-Id",
                "X-Payment-Signature",
            ],
        )

    @app.get("/health")
    async def health() -> dict:
        if settings.is_production:
            return {
                "status": "ok",
                "auth_required": settings.api_auth_required,
            }
        return {
            "status": "ok",
            "qdrant_url": settings.qdrant_url,
            "embedding_service_url": settings.embedding_service_url,
            "database": "configured",
            "storage_backend": settings.storage_backend,
            "object_storage_backend": settings.object_storage_backend,
            "object_storage_bucket": storage.bucket,
            "auth_required": settings.api_auth_required,
        }

    @app.post("/auth/dev-login", response_model=AuthTokenResponse)
    async def dev_login(request: DevLoginRequest, http_request: Request) -> AuthTokenResponse:
        if not settings.auth_dev_login_enabled:
            raise HTTPException(status_code=403, detail="开发登录未启用。")
        tenant_id = request.tenant_id or settings.default_tenant_id
        async with session_scope() as db:
            await _billing_service(db).get_or_create_account(
                tenant_id=tenant_id,
                user_id=request.user_id,
                display_name=request.display_name,
                platform=request.platform,
            )
        return await _issue_auth_response(
            tenant_id=tenant_id,
            user_id=request.user_id,
            platform=request.platform,
            display_name=request.display_name,
            http_request=http_request,
        )

    @app.post("/auth/register", response_model=AuthTokenResponse)
    async def register(request: RegisterRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "register", request.email)
        tenant_id = request.tenant_id or settings.default_tenant_id
        try:
            async with session_scope() as db:
                account = await _billing_service(db).register_with_password(
                    tenant_id=tenant_id,
                    email=request.email,
                    password=_password_secret(request),
                    display_name=request.display_name,
                    platform=request.platform,
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return await _issue_auth_response(
            tenant_id=tenant_id,
            user_id=account.user_id,
            platform=request.platform,
            display_name=account.display_name,
            http_request=http_request,
        )

    @app.post("/auth/login", response_model=AuthTokenResponse)
    async def password_login(request: PasswordLoginRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "login", request.email)
        tenant_id = request.tenant_id or settings.default_tenant_id
        blocked_by_ip = False
        async with session_scope() as db:
            security = SecurityService(db, tenant_id=tenant_id)
            ip_address = _client_ip(http_request)
            failed_user_id = f"email:{request.email.lower().strip()}"
            failed_count = await security.recent_event_count(
                event_type="login_failed",
                ip_address=ip_address,
                user_id=failed_user_id,
                minutes=60,
            )
            if failed_count >= settings.auth_max_failed_attempts_per_hour:
                await security.record_event(
                    user_id=failed_user_id,
                    event_type="login_blocked",
                    severity="critical",
                    ip_address=ip_address,
                    user_agent=_client_user_agent(http_request),
                    request_id=_request_id(http_request),
                    metadata={"reason": "too_many_failed_attempts"},
                )
                blocked_by_ip = True
                account = None
            else:
                billing = _billing_service(db)
                account = await billing.authenticate_password(
                    tenant_id=tenant_id,
                    email=request.email,
                    password=_password_secret(request),
                )
                derived_secret = _derived_password_secret(request)
                raw_secret = (request.password or "").strip()
                if account is None and raw_secret:
                    legacy_account = await billing.authenticate_password(
                        tenant_id=tenant_id,
                        email=request.email,
                        password=raw_secret,
                    )
                    if legacy_account is not None:
                        if derived_secret:
                            await billing.replace_password(
                                tenant_id=tenant_id,
                                email=request.email,
                                password=derived_secret,
                            )
                        account = legacy_account
            if blocked_by_ip:
                pass
            elif account is None:
                await security.record_event(
                    user_id=failed_user_id,
                    event_type="login_failed",
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=_client_user_agent(http_request),
                    request_id=_request_id(http_request),
                )
                new_failed_count = failed_count + 1
                if new_failed_count >= settings.auth_alert_failed_attempts_per_hour:
                    await security.record_event(
                        user_id=failed_user_id,
                        event_type="abnormal_login_alert",
                        severity="critical",
                        ip_address=ip_address,
                        user_agent=_client_user_agent(http_request),
                        request_id=_request_id(http_request),
                        metadata={"failed_attempts_last_hour": new_failed_count},
                    )
        if blocked_by_ip:
            raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试。")
        if account is None:
            raise HTTPException(status_code=401, detail="邮箱或密码错误。")
        return await _issue_auth_response(
            tenant_id=tenant_id,
            user_id=account.user_id,
            platform=request.platform,
            display_name=account.display_name,
            http_request=http_request,
        )

    @app.post("/auth/wechat/login", response_model=AuthTokenResponse)
    async def wechat_login(request: ProviderLoginRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "wechat-login", request.code[:32])
        if settings.wechat_app_id and settings.wechat_app_secret:
            try:
                session = await asyncio.to_thread(exchange_wechat_code, settings, request.code)
            except AuthProviderError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"微信登录服务不可用：{exc}") from exc
            async with session_scope() as db:
                await _billing_service(db).get_or_create_account(
                    tenant_id=request.tenant_id or settings.default_tenant_id,
                    user_id=f"wechat:{session.openid}",
                    display_name=request.display_name or "微信用户",
                    platform=request.platform or "miniapp",
                )
            return await _issue_auth_response(
                tenant_id=request.tenant_id or settings.default_tenant_id,
                user_id=f"wechat:{session.openid}",
                platform=request.platform or "miniapp",
                display_name=request.display_name or "微信用户",
                http_request=http_request,
            )
        if not settings.auth_mock_provider_login_enabled:
            raise HTTPException(status_code=501, detail="微信登录需要接入微信 code2session 后启用。")
        return await _issue_auth_response(
            tenant_id=request.tenant_id or settings.default_tenant_id,
            user_id=f"wechat:{request.code[:32]}",
            platform=request.platform or "miniapp",
            display_name=request.display_name or "微信用户",
            http_request=http_request,
        )

    @app.post("/auth/apple/login", response_model=AuthTokenResponse)
    async def apple_login(request: ProviderLoginRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "apple-login", request.code[:32])
        if not settings.auth_mock_provider_login_enabled:
            raise HTTPException(status_code=501, detail="Apple 登录需要接入 identityToken 校验后启用。")
        return await _issue_auth_response(
            tenant_id=request.tenant_id or settings.default_tenant_id,
            user_id=f"apple:{request.code[:32]}",
            platform=request.platform or "ios",
            display_name=request.display_name or "Apple 用户",
            http_request=http_request,
        )

    @app.post("/auth/phone/login", response_model=AuthTokenResponse)
    async def phone_login(request: PhoneLoginRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "phone-login", request.phone)
        if not settings.auth_mock_provider_login_enabled:
            raise HTTPException(status_code=501, detail="手机号登录需要接入短信验证码服务后启用。")
        if not request.verification_code:
            raise HTTPException(status_code=400, detail="验证码不能为空。")
        return await _issue_auth_response(
            tenant_id=request.tenant_id or settings.default_tenant_id,
            user_id=f"phone:{request.phone}",
            platform=request.platform,
            display_name="手机号用户",
            http_request=http_request,
        )

    @app.post("/auth/refresh", response_model=AuthTokenResponse)
    async def refresh_token(request: RefreshTokenRequest, http_request: Request) -> AuthTokenResponse:
        async with session_scope() as db:
            security = SecurityService(db, tenant_id=request.tenant_id or settings.default_tenant_id)
            try:
                current, refresh = await security.rotate_refresh_token(
                    refresh_token=request.refresh_token,
                    ttl_seconds=settings.auth_refresh_token_ttl_seconds,
                    ip_address=_client_ip(http_request),
                    user_agent=_client_user_agent(http_request),
                )
            except ValueError as exc:
                await security.record_event(
                    event_type="refresh_failed",
                    severity="warning",
                    ip_address=_client_ip(http_request),
                    user_agent=_client_user_agent(http_request),
                    request_id=_request_id(http_request),
                    metadata={"reason": str(exc)},
                )
                raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录。") from exc
            role = await security.get_role(current.user_id)
            snapshot = await _billing_service(db).account_snapshot(
                tenant_id=current.tenant_id,
                user_id=current.user_id,
            )
        token, expires_at = issue_client_token(
            settings,
            tenant_id=current.tenant_id,
            user_id=current.user_id,
            platform=current.platform,
            display_name=snapshot.display_name,
            role=role,
        )
        return AuthTokenResponse(
            access_token=token,
            refresh_token=refresh.token,
            expires_at=expires_at,
            refresh_expires_at=int(refresh.expires_at.timestamp()),
            tenant_id=current.tenant_id,
            user_id=current.user_id,
            platform=current.platform,
            role=role,
            display_name=snapshot.display_name,
            trial_uses_remaining=snapshot.trial_uses_remaining,
            credit_balance=str(snapshot.credit_balance),
        )

    @app.post("/auth/logout")
    async def logout(
        request: LogoutRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            security = SecurityService(db, tenant_id=context.tenant_id)
            if request.revoke_all or not request.refresh_token:
                revoked = await security.revoke_user_refresh_tokens(context.user_id)
            else:
                revoked = await security.revoke_refresh_token(request.refresh_token, user_id=context.user_id)
            await security.record_event(
                user_id=context.user_id,
                event_type="logout",
                severity="info",
                request_id=context.request_id,
                metadata={"revoke_all": request.revoke_all, "revoked_tokens": revoked},
            )
        return {"ok": True, "revoked_tokens": revoked}

    @app.get("/me", response_model=MeResponse)
    async def me(context: RequestContext = Depends(request_context)) -> MeResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            account = await _billing_service(db).account_snapshot(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        return MeResponse(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            platform=context.platform,
            role=context.role,
            authenticated=context.authenticated,
            trial_uses_remaining=account.trial_uses_remaining,
            credit_balance=str(account.credit_balance),
            credit_balance_micros=account.credit_balance_micros,
        )

    @app.get("/account", response_model=AccountResponse)
    async def account(context: RequestContext = Depends(request_context)) -> AccountResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            snapshot = await _billing_service(db).account_snapshot(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        return _account_response(snapshot, role=context.role)

    @app.get("/settings", response_model=UserSettingsResponse)
    async def get_user_settings(context: RequestContext = Depends(request_context)) -> UserSettingsResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            snapshot = await _billing_service(db).account_snapshot(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        return _settings_response(snapshot.settings)

    @app.put("/settings", response_model=UserSettingsResponse)
    async def update_user_settings(
        request: UpdateUserSettingsRequest,
        context: RequestContext = Depends(request_context),
    ) -> UserSettingsResponse:
        _require_authenticated(context)
        payload = {}
        if request.default_interview_mode is not None:
            payload["default_interview_mode"] = request.default_interview_mode
        async with session_scope() as db:
            snapshot = await _billing_service(db).update_account_settings(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                settings=payload,
            )
        return _settings_response(snapshot.settings)

    @app.get("/admin/security/events")
    async def admin_security_events(
        limit: int = Query(default=100, ge=1, le=500),
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_permission(context, "security:read")
        async with session_scope() as db:
            events = await SecurityService(db, tenant_id=context.tenant_id).list_events(limit=limit)
        return [security_event_to_dict(event) for event in events]

    @app.get("/admin/roles")
    async def admin_roles(
        context: RequestContext = Depends(request_context),
    ) -> list[dict]:
        _require_permission(context, "users:read")
        async with session_scope() as db:
            roles = await SecurityService(db, tenant_id=context.tenant_id).list_roles()
        return [role_assignment_to_dict(role) for role in roles]

    @app.post("/admin/roles/grant")
    async def admin_grant_role(
        request: RoleGrantRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_permission(context, "roles:write")
        async with session_scope() as db:
            await SecurityService(db, tenant_id=context.tenant_id).grant_role(
                user_id=request.user_id,
                role=request.role,
                granted_by=context.user_id,
                metadata=request.metadata,
            )
        return {"ok": True}

    @app.post("/admin/roles/revoke")
    async def admin_revoke_role(
        request: RoleRevokeRequest,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_permission(context, "roles:write")
        async with session_scope() as db:
            revoked = await SecurityService(db, tenant_id=context.tenant_id).revoke_role(
                user_id=request.user_id,
                role=request.role,
                revoked_by=context.user_id,
            )
        return {"ok": True, "revoked": revoked}

    @app.post("/account/recharge", response_model=AccountResponse)
    async def recharge(
        request: RechargeRequest,
        context: RequestContext = Depends(request_context),
    ) -> AccountResponse:
        _require_admin_or_mock_recharge(context, settings, request.payment_provider)
        target_user_id = _recharge_target_user_id(context, request.target_user_id)
        try:
            validate_recharge_amount(request.amount_credits, settings.max_recharge_credits)
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            async with session_scope() as db:
                snapshot = await _billing_service(db).recharge(
                    tenant_id=context.tenant_id,
                    user_id=target_user_id,
                    amount_credits=request.amount_credits,
                    payment_provider=request.payment_provider,
                    external_order_id=request.external_order_id,
                    metadata={
                        "source": "manual_recharge",
                        "operator_user_id": context.user_id,
                        "operator_role": context.role,
                        **request.metadata,
                    },
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _account_response(snapshot, role=context.role)

    @app.post("/payments/orders", response_model=PaymentOrderResponse)
    async def create_payment_order(
        request: CreatePaymentOrderRequest,
        context: RequestContext = Depends(request_context),
    ) -> PaymentOrderResponse:
        _require_authenticated(context)
        provider = request.payment_provider.strip().lower()
        if provider in {"mock", "dev"} and settings.is_production:
            raise HTTPException(status_code=400, detail="生产环境不允许创建 mock 支付订单。")
        if request.metadata and len(json.dumps(request.metadata, ensure_ascii=False)) > 4096:
            raise HTTPException(status_code=413, detail="支付订单 metadata 过大。")
        try:
            validate_recharge_amount(request.amount_credits, settings.max_recharge_credits)
            async with session_scope() as db:
                billing = _billing_service(db)
                plan = None
                if request.plan_code:
                    try:
                        plan = await AdminConsoleService(
                            db,
                            tenant_id=context.tenant_id,
                            actor_id="system",
                        ).get_enabled_plan(request.plan_code)
                    except LookupError as exc:
                        raise HTTPException(status_code=400, detail=str(exc)) from exc
                    if Decimal(plan["price_credits"]) != request.amount_credits:
                        raise HTTPException(status_code=400, detail="套餐价格已变化，请刷新后重试。")
                order = await billing.create_payment_order(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    amount_credits=request.amount_credits,
                    credited_amount=plan["included_credits"] if plan else request.amount_credits,
                    payment_provider=provider,
                    external_order_id=request.external_order_id,
                    metadata={
                        "source": "client_order",
                        "platform": context.platform,
                        "plan_code": request.plan_code,
                        **request.metadata,
                    },
                )
                if provider == "alipay":
                    initiated = await asyncio.to_thread(
                        create_alipay_page_pay,
                        settings,
                        external_order_id=order.external_order_id,
                        amount_credits=request.amount_credits,
                        subject=f"Interview Agent 积分充值 {request.amount_credits}",
                    )
                    order = await billing.update_payment_order_metadata(
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                        external_order_id=order.external_order_id,
                        status=initiated.status,
                        metadata={
                            "pay_url": initiated.pay_url,
                            "provider_payload": initiated.raw or {},
                        },
                    )
                elif provider == "wechat":
                    initiated = await asyncio.to_thread(
                        create_wechat_native_pay,
                        settings,
                        external_order_id=order.external_order_id,
                        amount_credits=request.amount_credits,
                        description=f"Interview Agent 积分充值 {request.amount_credits}",
                    )
                    order = await billing.update_payment_order_metadata(
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                        external_order_id=order.external_order_id,
                        status=initiated.status,
                        metadata={
                            "code_url": initiated.code_url,
                            "provider_payload": initiated.raw or {},
                        },
                    )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PaymentProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _payment_order_response(order)

    @app.get("/payments/orders/{external_order_id}", response_model=PaymentOrderResponse)
    async def get_payment_order(
        external_order_id: str,
        context: RequestContext = Depends(request_context),
    ) -> PaymentOrderResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            order = await _billing_service(db).get_payment_order(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                external_order_id=external_order_id,
            )
        if not order:
            raise HTTPException(status_code=404, detail="payment order not found")
        return _payment_order_response(order)

    @app.post("/payments/webhook", response_model=PaymentWebhookResponse)
    async def payment_webhook(request: Request) -> PaymentWebhookResponse:
        body = await request.body()
        _verify_payment_signature(
            body,
            request.headers.get("X-Payment-Signature"),
            settings.payment_webhook_secret,
        )
        try:
            payload = PaymentWebhookPayload.model_validate_json(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="支付回调 JSON 无效。") from exc
        _validate_payment_webhook_payload(payload, settings)
        status_value = payload.status.strip().lower()
        if status_value not in {"paid", "success", "succeeded"}:
            return PaymentWebhookResponse(
                accepted=True,
                applied=False,
                status=status_value,
                external_order_id=payload.external_order_id,
            )

        try:
            async with session_scope() as db:
                billing = _billing_service(db)
                recharge_result = await billing.apply_paid_order(
                    tenant_id=payload.tenant_id,
                    user_id=payload.user_id,
                    amount_credits=payload.amount_credits,
                    payment_provider=payload.payment_provider,
                    external_order_id=payload.external_order_id,
                    metadata={
                        "payment_status": status_value,
                        "currency": payload.currency,
                        **payload.metadata,
                    },
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PaymentWebhookResponse(
            accepted=True,
            applied=recharge_result.created,
            status=status_value,
            external_order_id=payload.external_order_id,
            account=_account_response(recharge_result.account),
        )

    @app.post("/payments/alipay/notify")
    async def alipay_notify(request: Request) -> Response:
        body = await request.body()
        params = {
            key: values[-1]
            for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()
            if values
        }
        if not settings.alipay_public_key:
            raise HTTPException(status_code=503, detail="ALIPAY_PUBLIC_KEY 未配置。")
        if not verify_alipay_notify(params, settings.alipay_public_key):
            raise HTTPException(status_code=400, detail="支付宝回调验签失败。")
        trade_status = params.get("trade_status", "")
        if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
            return Response("success", media_type="text/plain")
        external_order_id = params.get("out_trade_no", "")
        amount = Decimal(params.get("total_amount", "0"))
        try:
            async with session_scope() as db:
                order = await _find_payment_order_for_webhook(db, external_order_id)
                if not order:
                    raise HTTPException(status_code=404, detail="支付订单不存在。")
                await _billing_service(db).apply_paid_order(
                    tenant_id=order.tenant_id,
                    user_id=order.user_id,
                    amount_credits=amount,
                    payment_provider="alipay",
                    external_order_id=external_order_id,
                    metadata={
                        "trade_no": params.get("trade_no", ""),
                        "buyer_logon_id": params.get("buyer_logon_id", ""),
                        "source": "alipay_notify",
                    },
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response("success", media_type="text/plain")

    @app.post("/payments/wechat/notify")
    async def wechat_notify(request: Request) -> JSONResponse:
        if not settings.wechat_pay_api_v3_key:
            raise HTTPException(status_code=503, detail="WECHAT_PAY_API_V3_KEY 未配置。")
        if not settings.wechat_pay_platform_cert_pem:
            raise HTTPException(status_code=503, detail="WECHAT_PAY_PLATFORM_CERT_PEM 未配置。")
        body = await request.body()
        if not verify_wechat_notify(request.headers, body, settings.wechat_pay_platform_cert_pem):
            raise HTTPException(status_code=400, detail="微信支付回调验签失败。")
        payload = json.loads(body.decode("utf-8"))
        resource = payload.get("resource")
        if not isinstance(resource, dict):
            raise HTTPException(status_code=400, detail="微信支付回调 resource 无效。")
        try:
            transaction = decrypt_wechat_resource(resource, settings.wechat_pay_api_v3_key)
        except PaymentProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if transaction.get("trade_state") != "SUCCESS":
            return JSONResponse({"code": "SUCCESS", "message": "成功"})
        external_order_id = transaction.get("out_trade_no", "")
        amount = Decimal(str(transaction.get("amount", {}).get("total", 0))) / Decimal("100")
        try:
            async with session_scope() as db:
                order = await _find_payment_order_for_webhook(db, external_order_id)
                if not order:
                    raise HTTPException(status_code=404, detail="支付订单不存在。")
                await _billing_service(db).apply_paid_order(
                    tenant_id=order.tenant_id,
                    user_id=order.user_id,
                    amount_credits=amount,
                    payment_provider="wechat",
                    external_order_id=external_order_id,
                    metadata={
                        "transaction_id": transaction.get("transaction_id", ""),
                        "trade_state": transaction.get("trade_state", ""),
                        "source": "wechat_notify",
                    },
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse({"code": "SUCCESS", "message": "成功"})

    @app.post("/resume/parse", response_model=ResumeParseResponse)
    async def parse_resume(
        request: ResumeParseRequest,
        http_request: Request,
        context: RequestContext = Depends(request_context),
    ) -> ResumeParseResponse:
        _require_authenticated(context)
        _check_base64_size(request.content_base64, settings.max_upload_bytes)
        await _scan_upload_or_raise(
            filename=request.filename,
            content_base64=request.content_base64,
            context=context,
            request=http_request,
        )
        try:
            parsed = parse_resume_base64(request.filename, request.content_base64)
        except ResumeParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ResumeParseResponse(
            filename=parsed.filename,
            file_type=parsed.file_type,
            text=parsed.text,
            summary=parsed.summary,
            truncated=parsed.truncated,
        )

    @app.post("/resumes", response_model=ResumeRecordResponse)
    async def import_resume(
        request: ResumeImportRequest,
        http_request: Request,
        context: RequestContext = Depends(request_context),
    ) -> ResumeRecordResponse:
        _require_authenticated(context)
        _check_base64_size(request.content_base64, settings.max_upload_bytes)
        await _scan_upload_or_raise(
            filename=request.filename,
            content_base64=request.content_base64,
            context=context,
            request=http_request,
        )
        try:
            async with session_scope() as db:
                stored = await ResumeService(
                    db,
                    storage,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    max_upload_bytes=settings.max_upload_bytes,
                    store_source_path=settings.store_upload_source_path,
                ).save_base64(
                    request.filename,
                    request.content_base64,
                    source_path=request.source_path,
                )
        except (ResumeParseError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"简历存储服务不可用：{exc}") from exc
        return ResumeRecordResponse(**stored_resume_to_payload(stored))

    @app.get("/resumes", response_model=list[ResumeRecordResponse])
    async def list_resumes(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[ResumeRecordResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            resumes = await ResumeService(
                db,
                storage,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list(limit=limit, offset=offset)
        return [ResumeRecordResponse(**stored_resume_to_payload(item)) for item in resumes]

    @app.get("/resumes/{resume_id}", response_model=ResumeRecordResponse)
    async def get_resume(
        resume_id: str,
        context: RequestContext = Depends(request_context),
    ) -> ResumeRecordResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            stored = await ResumeService(
                db,
                storage,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get(resume_id)
        if not stored:
            raise HTTPException(status_code=404, detail="resume not found")
        return ResumeRecordResponse(**stored_resume_to_payload(stored))

    @app.delete("/resumes/{resume_id}", response_model=DeleteResponse)
    async def delete_resume(
        resume_id: str,
        context: RequestContext = Depends(request_context),
    ) -> DeleteResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            deleted = await ResumeService(
                db,
                storage,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).delete(resume_id)
        return DeleteResponse(deleted=deleted)

    @app.post("/sessions", response_model=ChatResponse)
    async def create_session(
        request: SessionRequest,
        context: RequestContext = Depends(request_context),
    ) -> ChatResponse:
        _require_authenticated(context)
        _check_session_request(request, settings.max_message_chars)
        stored_resume = await _load_owned_resume(request.resume_id, storage, context)
        config = apply_session_request(load_config(None), request, stored_resume=stored_resume)
        async with session_scope() as db:
            if request.interviewer_kit_id:
                try:
                    await InterviewerWorkspaceService(
                        db,
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                    ).require_owned_kit(request.interviewer_kit_id)
                except LookupError as exc:
                    raise HTTPException(status_code=404, detail="interviewer kit not found") from exc
            try:
                model_id = await _billing_service(db).resolve_model_id(
                    tenant_id=context.tenant_id,
                    requested=request.model_id,
                    fallback=_resolve_model_id(None),
                )
                await _billing_service(db).ensure_can_use(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    model_id=model_id,
                )
            except InsufficientCreditsError as exc:
                raise HTTPException(status_code=402, detail=str(exc)) from exc
            except BillingError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        harness = _create_harness(
            config,
            offline=request.offline,
            web_search_enabled=request.web_search,
            model_id=model_id,
            thinking_enabled=request.thinking_enabled,
            reasoning_effort=request.reasoning_effort,
        )
        session_id = str(uuid4())
        loop = AgentLoop(config, harness)
        loop.set_thread_id(session_id)
        result = loop.start()
        result.orchestration = loop.orchestration_status
        usage = await _record_usage(
            session_id=session_id,
            event_type="start",
            model_id=model_id,
            prompt_text=_usage_prompt_text(config, request),
            response_text=result.message,
            result=result,
            context=context,
        )
        sessions[session_id] = ApiSession(
            loop=loop,
            config=config,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            model_id=model_id,
            offline=request.offline,
            web_search_enabled=request.web_search,
            resume_id=request.resume_id,
            plan_task_id=request.plan_task_id,
            interviewer_kit_id=request.interviewer_kit_id,
        )
        await _persist_interview_result(
            session_id,
            config,
            result,
            "start",
            request.resume_id,
            context.tenant_id,
            context.user_id,
            plan_task_id=request.plan_task_id,
            interviewer_kit_id=request.interviewer_kit_id,
        )
        return _response(session_id, result, model_id=model_id, usage=usage)

    @app.get("/sessions", response_model=list[SessionSummaryResponse])
    async def list_sessions(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> list[SessionSummaryResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            records = await InterviewPersistenceService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_sessions(limit=limit, offset=offset)
        return [SessionSummaryResponse(**record) for record in records]

    @app.get("/sessions/{session_id}", response_model=SessionDetailResponse)
    async def get_session(
        session_id: str,
        context: RequestContext = Depends(request_context),
    ) -> SessionDetailResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            record = await InterviewPersistenceService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get_session_record(session_id)
        if not record:
            raise HTTPException(status_code=404, detail="session not found")
        return SessionDetailResponse(**record)

    @app.delete("/sessions/{session_id}", response_model=DeleteResponse)
    async def delete_session(
        session_id: str,
        context: RequestContext = Depends(request_context),
    ) -> DeleteResponse:
        _require_authenticated(context)
        async with session_scope() as db:
            deleted = await InterviewPersistenceService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).delete_session(session_id)
        if deleted:
            sessions.pop(session_id, None)
        return DeleteResponse(deleted=deleted)

    @app.post("/sessions/{session_id}/rewind", response_model=SessionDetailResponse)
    async def rewind_session(
        session_id: str,
        request: SessionRewindRequest,
        context: RequestContext = Depends(request_context),
    ) -> SessionDetailResponse:
        _require_authenticated(context)
        session = await _get_or_restore_session(session_id, context.tenant_id, context.user_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        if request.turn_index > len(session.loop.state.turns):
            raise HTTPException(status_code=400, detail="turn index out of range")

        state = session.loop.state.model_copy(deep=True)
        if session.config.mode == InterviewMode.CANDIDATE:
            state.turns = state.turns[: request.turn_index - 1]
        else:
            state.turns = state.turns[: request.turn_index]
            state.turns[-1].candidate = None
        state.completed = False
        state.last_answer_assessment = ""
        state.stage = state.turns[-1].stage if state.turns else InterviewStage.INTRO
        session.loop.state = state

        async with session_scope() as db:
            service = InterviewPersistenceService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            await service.sync_state(
                session_id=session_id,
                config=session.config,
                state=state,
            )
            record = await service.get_session_record(session_id)
        if not record:
            raise HTTPException(status_code=404, detail="session not found")
        return SessionDetailResponse(**record)

    @app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
    async def send_message(
        session_id: str,
        request: MessageRequest,
        context: RequestContext = Depends(request_context),
    ) -> ChatResponse:
        _require_authenticated(context)
        _check_message(request.message, settings.max_message_chars)
        session = await _get_or_restore_session(session_id, context.tenant_id, context.user_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        try:
            async with session_scope() as db:
                await _billing_service(db).ensure_can_use(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    model_id=session.model_id,
                )
        except InsufficientCreditsError as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = session.loop.step(request.message)
        usage = await _record_usage(
            session_id=session_id,
            event_type="turn",
            model_id=session.model_id,
            prompt_text=request.message,
            response_text=result.message,
            result=result,
            context=context,
        )
        await _persist_interview_result(
            session_id,
            session.config,
            result,
            "turn",
            session.resume_id,
            context.tenant_id,
            context.user_id,
            plan_task_id=session.plan_task_id,
            interviewer_kit_id=session.interviewer_kit_id,
        )
        return _response(session_id, result, model_id=session.model_id, usage=usage)

    @app.post("/sessions/{session_id}/stream")
    async def stream_message(
        session_id: str,
        message_request: MessageRequest,
        http_request: Request,
        context: RequestContext = Depends(request_context),
    ) -> StreamingResponse:
        request_id = _request_id(http_request)
        _require_authenticated(context)
        _check_message(message_request.message, settings.max_message_chars)
        session = await _get_or_restore_session(session_id, context.tenant_id, context.user_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        try:
            async with session_scope() as db:
                await _billing_service(db).ensure_can_use(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    model_id=session.model_id,
                )
        except InsufficientCreditsError as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        async def event_stream():
            logger.info(
                "stream_open request_id=%s session_id=%s user_id=%s model_id=%s message_chars=%s",
                request_id,
                session_id,
                context.user_id,
                session.model_id,
                len(message_request.message),
            )
            yield _sse("stream.ready", {"request_id": request_id, "session_id": session_id})
            yield _sse("tool.notice", {"message": "开始分析回答。"})
            previous_state = session.loop.state.model_copy(deep=True)
            llm_started = time.perf_counter()
            heartbeat_interval_seconds = 3
            heartbeat_count = 0
            delta_count = 0
            delta_queue: Queue[str] = Queue()

            def publish_delta(text: str) -> None:
                if text:
                    delta_queue.put(text)

            logger.info(
                "stream_llm_start request_id=%s session_id=%s model_id=%s turn_count=%s",
                request_id,
                session_id,
                session.model_id,
                len(previous_state.turns),
            )
            llm_task = asyncio.create_task(
                asyncio.to_thread(session.loop.step_stream, message_request.message, publish_delta)
            )
            try:
                while True:
                    while True:
                        try:
                            delta = delta_queue.get_nowait()
                        except Empty:
                            break
                        delta_count += 1
                        if not await http_request.is_disconnected():
                            yield _sse("message.delta", {"text": delta})
                    if llm_task.done():
                        break
                    try:
                        await asyncio.wait_for(asyncio.shield(llm_task), timeout=heartbeat_interval_seconds)
                    except asyncio.TimeoutError:
                        pass
                    if llm_task.done():
                        continue
                    heartbeat_count += 1
                    elapsed_seconds = round(time.perf_counter() - llm_started, 1)
                    disconnected = await http_request.is_disconnected()
                    logger.info(
                        "stream_heartbeat request_id=%s session_id=%s model_id=%s elapsed_seconds=%s disconnected=%s",
                        request_id,
                        session_id,
                        session.model_id,
                        elapsed_seconds,
                        disconnected,
                    )
                    if not disconnected:
                        yield _sse(
                            "heartbeat",
                            {
                                "status": "running",
                                "elapsed_seconds": elapsed_seconds,
                            },
                        )
                while True:
                    try:
                        delta = delta_queue.get_nowait()
                    except Empty:
                        break
                    delta_count += 1
                    if not await http_request.is_disconnected():
                        yield _sse("message.delta", {"text": delta})
                result = await llm_task
            except Exception as exc:
                logger.exception(
                    "stream_llm_error request_id=%s session_id=%s model_id=%s duration_ms=%s",
                    request_id,
                    session_id,
                    session.model_id,
                    round((time.perf_counter() - llm_started) * 1000, 2),
                )
                if not await http_request.is_disconnected():
                    yield _sse(
                        "message.error",
                        {
                            "message": "模型生成失败，请稍后重试。",
                            "detail": str(exc)[:240],
                            "request_id": request_id,
                        },
                    )
                return
            logger.info(
                "stream_llm_done request_id=%s session_id=%s model_id=%s duration_ms=%s fallback_used=%s completed=%s heartbeats=%s deltas=%s",
                request_id,
                session_id,
                session.model_id,
                round((time.perf_counter() - llm_started) * 1000, 2),
                result.fallback_used,
                result.state.completed,
                heartbeat_count,
                delta_count,
            )
            client_disconnected = await http_request.is_disconnected()
            if client_disconnected:
                logger.warning(
                    "stream_client_disconnected request_id=%s session_id=%s model_id=%s phase=after_llm will_persist=true",
                    request_id,
                    session_id,
                    session.model_id,
                )
            persist_started = time.perf_counter()
            logger.info(
                "stream_persist_start request_id=%s session_id=%s model_id=%s",
                request_id,
                session_id,
                session.model_id,
            )
            usage = await _record_usage(
                session_id=session_id,
                event_type="turn",
                model_id=session.model_id,
                prompt_text=message_request.message,
                response_text=result.message,
                result=result,
                context=context,
            )
            await _persist_interview_result(
                session_id,
                session.config,
                result,
                "turn",
                session.resume_id,
                context.tenant_id,
                context.user_id,
                plan_task_id=session.plan_task_id,
                interviewer_kit_id=session.interviewer_kit_id,
            )
            logger.info(
                "stream_persist_done request_id=%s session_id=%s model_id=%s duration_ms=%s",
                request_id,
                session_id,
                session.model_id,
                round((time.perf_counter() - persist_started) * 1000, 2),
            )
            for finding in result.guardrail_findings or []:
                if not client_disconnected:
                    yield _sse("guardrail.notice", {"message": finding.message})
            if not client_disconnected:
                yield _sse(
                    "message.done",
                    {
                        "session_id": session_id,
                        "message": result.message,
                        "completed": result.state.completed,
                        "fallback_used": result.fallback_used,
                        "guardrails": [finding.message for finding in result.guardrail_findings or []],
                        "model_id": session.model_id,
                        "usage": usage.model_dump(mode="json") if usage else None,
                        "turn_index": len(result.state.turns) or None,
                        "orchestration": result.orchestration,
                    },
                )
            else:
                logger.warning(
                    "stream_done_not_sent request_id=%s session_id=%s model_id=%s persisted=true",
                    request_id,
                    session_id,
                    session.model_id,
                )
                return
            logger.info(
                "stream_done_sent request_id=%s session_id=%s model_id=%s",
                request_id,
                session_id,
                session.model_id,
            )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/sessions/{session_id}/transcript")
    async def transcript(
        session_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        session = await _get_or_restore_session(session_id, context.tenant_id, context.user_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        return {"transcript": session.loop.state.transcript()}

    @app.get("/interview-reports")
    async def list_interview_reports(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            service = InterviewReportService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            )
            return await service.list_reports(limit=limit, offset=offset)

    @app.get("/interview-reports/{session_id}")
    async def get_interview_report(
        session_id: str,
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            service = InterviewReportService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            )
            report = await service.get_report(session_id)
        if not report:
            raise HTTPException(status_code=404, detail="interview report not found")
        return report

    @app.post("/review-site/plans/{plan_id}/report-tasks")
    async def create_tasks_from_report(
        plan_id: str,
        payload: dict = Body(default={}),
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        async with session_scope() as db:
            service = InterviewReportService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            )
            try:
                result = await service.add_tasks_from_report(
                    plan_id=plan_id, session_id=session_id
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "ok", "data": result}

    @app.post("/admin/test-data/review-site")
    async def create_review_site_test_data(
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        if context.role not in {"admin", "server"}:
            raise HTTPException(status_code=403, detail="只有管理员可以创建测试数据。")
        if settings.is_production:
            raise HTTPException(status_code=403, detail="生产环境禁止创建测试数据。")
        async with session_scope() as db:
            service = AdminTestDataService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            return await service.ensure_review_site_fixture()

    @app.post("/review-site/planner/generate", response_model=PlanGenerateResponse)
    async def generate_review_plan(
        request: PlanGenerateRequest,
        context: RequestContext = Depends(request_context),
    ) -> PlanGenerateResponse:
        _require_authenticated(context)
        total_days = request.total_days
        hours_per_day = request.hours_per_day

        # 优先 LLM 个性化生成（结合简历/历史报告/错题本）；离线、余额不足或失败时自动降级规则模板
        async with session_scope() as db:
            llm_plan = await _try_generate_llm_plan(db, request, context)
        if llm_plan is not None:
            return PlanGenerateResponse(
                plan_id=llm_plan["plan_id"],
                estimated_daily_hours=round(hours_per_day, 1),
                breakdown_phases=llm_plan["breakdown"],
                generated_by="llm",
            )

        phases_def = [
            ("p1", "基础储备", 0.22, "简历与自我介绍背诵、素材与题库第一轮通读。"),
            ("p2", "深挖对齐", 0.28, "项目深挖 STAR 打磨、公司专项题库与答题指南。"),
            ("p3", "模拟冲刺", 0.28, "多场全真模拟、错题本清零、弱点清单二刷。"),
            ("p4", "面试前速记", 0.22, "A4 速记单、定制公司面、错题回顾、状态管理。"),
        ]
        breakdown: list[dict] = []
        cursor = 0
        phases_data: list[dict] = []
        days_data: list[dict] = []
        tasks_per_day: dict[str, list[dict]] = {}

        for idx, (phase_key, phase_title, ratio, phase_goal) in enumerate(phases_def):
            phase_days = max(1, round(total_days * ratio))
            if idx == len(phases_def) - 1:
                phase_days = total_days - cursor
            start_day = cursor + 1
            end_day = cursor + phase_days
            range_label = f"Day{start_day}-{end_day}" if start_day != end_day else f"Day{start_day}"
            phases_data.append({
                "id": phase_key,
                "title": phase_title,
                "range": range_label,
                "goal": phase_goal,
            })
            breakdown.append({
                "phase_key": phase_key,
                "title": phase_title,
                "range_label": range_label,
                "days": phase_days,
                "estimated_hours": round(phase_days * hours_per_day, 1),
                "goal": phase_goal,
            })
            for day_offset in range(phase_days):
                day_num = cursor + day_offset + 1
                day_key = f"day-{day_num}"
                day_label = f"Day {day_num}"
                day_title = _generate_day_title(phase_key, day_offset + 1, phase_days, request.target_role, request.focus_areas)
                days_data.append({
                    "id": day_key,
                    "day": day_label,
                    "phase": phase_key,
                    "title": day_title,
                })
                tasks_per_day[day_key] = _generate_day_tasks(
                    day_key=day_key,
                    phase_key=phase_key,
                    day_offset=day_offset,
                    phase_days=phase_days,
                    target_role=request.target_role,
                    focus_areas=request.focus_areas,
                )
            cursor += phase_days

        plan_key = f"generated-{total_days}d-{int(time.time())}"
        title = (request.target_role or "面试") + f" {total_days} 天复习计划"
        if request.seniority:
            title += f" ({request.seniority})"
        plan_data = {
            "plan_key": plan_key,
            "title": title,
            "subtitle": f"总时长 {total_days} 天 × 日均 {hours_per_day}h",
            "description": _generate_plan_description(request),
            "status": "draft",
            "source_root": "",
            "source_documents": [],
            "commercial_positioning": [],
            "metadata": {
                "generated": True,
                "target_role": request.target_role,
                "seniority": request.seniority,
                "target_company": request.target_company or "",
                "total_days": total_days,
                "hours_per_day": hours_per_day,
                "focus_areas": request.focus_areas or [],
            },
        }
        async with session_scope() as db:
            repo = ReviewSiteRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            plan = await repo.create_plan(
                plan_data=plan_data,
                phases=phases_data,
                days=days_data,
                tasks_per_day=tasks_per_day,
                intro_scripts=[],
                star_cards=[],
                a4_memory=[],
            )
        return PlanGenerateResponse(
            plan_id=str(plan.id),
            estimated_daily_hours=round(hours_per_day, 1),
            breakdown_phases=breakdown,
        )

    return app


def _password_secret(request: RegisterRequest | PasswordLoginRequest) -> str:
    derived_secret = _derived_password_secret(request)
    if derived_secret:
        return derived_secret
    return (getattr(request, "password", "") or "").strip()


def _derived_password_secret(request: RegisterRequest | PasswordLoginRequest) -> str:
    scheme = (getattr(request, "password_scheme", "") or "").strip()
    derived = (getattr(request, "password_derived", "") or "").strip()
    if scheme == "client_sha256_v1" and re.fullmatch(r"[a-f0-9]{64}", derived):
        return f"{scheme}${derived}"
    email = (getattr(request, "email", "") or "").strip().lower()
    password = (getattr(request, "password", "") or "").strip()
    if email and password:
        digest = hashlib.sha256(
            f"interview-agent:password:v1:{email}\0{password}".encode("utf-8")
        ).hexdigest()
        return f"client_sha256_v1${digest}"
    return ""


async def _issue_auth_response(
    *,
    tenant_id: str,
    user_id: str,
    platform: str,
    display_name: str,
    http_request: Request | None = None,
) -> AuthTokenResponse:
    settings = load_settings()
    try:
        async with session_scope() as db:
            security = SecurityService(db, tenant_id=tenant_id)
            role = await security.get_role(user_id)
            refresh = await security.issue_refresh_token(
                user_id=user_id,
                platform=platform,
                ttl_seconds=settings.auth_refresh_token_ttl_seconds,
                ip_address=_client_ip(http_request) if http_request else None,
                user_agent=_client_user_agent(http_request) if http_request else None,
            )
            snapshot = await _billing_service(db).account_snapshot(tenant_id=tenant_id, user_id=user_id)
        token, expires_at = issue_client_token(
            settings,
            tenant_id=tenant_id,
            user_id=user_id,
            platform=platform,
            display_name=display_name,
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthTokenResponse(
        access_token=token,
        refresh_token=refresh.token,
        expires_at=expires_at,
        refresh_expires_at=int(refresh.expires_at.timestamp()),
        tenant_id=tenant_id,
        user_id=user_id,
        platform=platform,
        role=role,
        display_name=display_name,
        trial_uses_remaining=snapshot.trial_uses_remaining,
        credit_balance=str(snapshot.credit_balance),
    )


def apply_session_request(
    config: InterviewConfig,
    request: SessionRequest,
    *,
    stored_resume=None,
) -> InterviewConfig:
    resume_summary = stored_resume.summary if stored_resume is not None else _clean(request.resume_summary)
    resume_text = stored_resume.text if stored_resume is not None else _clean(request.resume_text)
    candidate = config.candidate.model_copy(
        update={
            key: value
            for key, value in {
                "name": _clean(request.candidate_name),
                "target_role": _clean(request.target_role),
                "seniority": _clean(request.seniority),
                "resume_summary": resume_summary,
                "resume_text": resume_text,
                "project_experience": _clean(request.project_experience),
                "interview_goal": _clean(request.interview_goal),
            }.items()
            if value
        }
    )
    updates: dict = {"candidate": CandidateProfile.model_validate(candidate)}
    if request.model_id:
        updates["model_id"] = _resolve_model_id(request.model_id)
    if request.mode:
        updates["mode"] = _parse_mode(request.mode)
    if request.industry:
        updates["industry"] = _parse_industry(request.industry)
    if request.focus_areas:
        focus_areas = [item.strip() for item in request.focus_areas if item and item.strip()]
        if focus_areas:
            updates["focus_areas"] = focus_areas
    return config.model_copy(update=updates)


def _parse_mode(value: str) -> InterviewMode:
    try:
        return InterviewMode(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="不支持的面试模式。") from exc


def _parse_industry(value: str) -> Industry:
    try:
        return Industry(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="不支持的行业。") from exc


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_authenticated(context: RequestContext) -> None:
    if not context.authenticated or context.user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="请先登录后再继续。",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _require_admin_or_mock_recharge(context: RequestContext, settings, payment_provider: str) -> None:
    _require_authenticated(context)
    provider = payment_provider.strip().lower()
    if context.role in {"admin", "server"}:
        return
    if settings.allow_mock_recharge and not settings.is_production and provider in {"mock", "dev", "manual"}:
        return
    raise HTTPException(status_code=403, detail="充值入账只能由管理员或已签名支付回调完成。")


def _require_permission(context: RequestContext, permission: str) -> None:
    _require_authenticated(context)
    if not has_permission(context.role, permission):
        raise HTTPException(status_code=403, detail="当前账号没有权限执行该操作。")


async def _scan_upload_or_raise(
    *,
    filename: str,
    content_base64: str,
    context: RequestContext,
    request: Request | None = None,
) -> None:
    settings = load_settings()
    result = scan_upload_content(filename=filename, content_base64=content_base64, settings=settings)
    if not result.findings:
        return
    async with session_scope() as db:
        await SecurityService(db, tenant_id=context.tenant_id).record_event(
            user_id=context.user_id,
            event_type="upload_security_scan",
            severity="critical" if result.blocked else "warning",
            ip_address=_client_ip(request) if request else None,
            user_agent=_client_user_agent(request) if request else None,
            request_id=context.request_id,
            metadata={
                "filename": filename,
                "score": result.score,
                "findings": [finding.__dict__ for finding in result.findings],
            },
        )
    if result.blocked:
        raise HTTPException(status_code=400, detail="上传内容未通过安全扫描，请检查文件后再试。")


def _recharge_target_user_id(context: RequestContext, target_user_id: str | None) -> str:
    cleaned = (target_user_id or context.user_id).strip()
    if context.role != "admin" and cleaned != context.user_id:
        raise HTTPException(status_code=403, detail="不能为其他用户充值。")
    if not _valid_subject_id(cleaned):
        raise HTTPException(status_code=400, detail="用户 ID 无效。")
    return cleaned


async def _load_owned_resume(
    resume_id: str | None,
    storage: ObjectStorage,
    context: RequestContext,
) -> StoredResume | None:
    if not resume_id:
        return None
    try:
        async with session_scope() as db:
            stored = await ResumeService(
                db,
                storage,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).get(resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="简历 ID 无效。") from exc
    if stored is None:
        raise HTTPException(status_code=404, detail="resume not found")
    return stored


def _verify_payment_signature(body: bytes, signature: str | None, secret: str) -> None:
    if not secret:
        raise HTTPException(status_code=503, detail="支付回调密钥未配置。")
    if not signature:
        raise HTTPException(status_code=401, detail="缺少支付回调签名。")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    candidates = {signature.strip()}
    if signature.startswith("sha256="):
        candidates.add(signature.removeprefix("sha256=").strip())
    if not any(hmac.compare_digest(candidate, expected) for candidate in candidates):
        raise HTTPException(status_code=401, detail="支付回调签名无效。")


def _validate_payment_webhook_payload(payload: PaymentWebhookPayload, settings) -> None:
    if not _valid_tenant_id(payload.tenant_id):
        raise HTTPException(status_code=400, detail="租户 ID 无效。")
    if not _valid_subject_id(payload.user_id):
        raise HTTPException(status_code=400, detail="用户 ID 无效。")
    provider = payload.payment_provider.strip().lower()
    if provider in {"mock", "dev"} and settings.is_production:
        raise HTTPException(status_code=400, detail="生产环境不接受 mock 支付回调。")
    if not re.fullmatch(r"[a-zA-Z0-9_.:@-]{1,64}", provider):
        raise HTTPException(status_code=400, detail="支付渠道无效。")
    if not re.fullmatch(r"[a-zA-Z0-9_.:@/-]{1,128}", payload.external_order_id.strip()):
        raise HTTPException(status_code=400, detail="支付订单号无效。")
    if payload.currency.strip().upper() != "CREDIT":
        raise HTTPException(status_code=400, detail="暂不支持该支付币种。")
    try:
        validate_recharge_amount(payload.amount_credits, settings.max_recharge_credits)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if len(json.dumps(payload.metadata, ensure_ascii=False)) > 4096:
        raise HTTPException(status_code=413, detail="支付回调 metadata 过大。")


def _valid_tenant_id(value: str) -> bool:
    return bool(re.fullmatch(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$", value))


def _valid_subject_id(value: str) -> bool:
    return bool(re.fullmatch(r"^[a-zA-Z0-9][a-zA-Z0-9_:@.+\-]{0,127}$", value))


async def _persist_interview_result(
    session_id: str,
    config: InterviewConfig,
    result,
    event_type: str,
    resume_id: str | None,
    tenant_id: str,
    user_id: str,
    plan_task_id: str | None = None,
    interviewer_kit_id: str | None = None,
) -> None:
    guardrails = [finding.message for finding in result.guardrail_findings or []]
    try:
        async with session_scope() as db:
            service = InterviewPersistenceService(db, tenant_id=tenant_id, user_id=user_id)
            if event_type == "start":
                await service.create_session(
                    session_id=session_id,
                    config=config,
                    state=result.state,
                    resume_id=resume_id,
                    plan_task_id=plan_task_id,
                    interviewer_kit_id=interviewer_kit_id,
                )
            await service.persist_turn(
                session_id=session_id,
                config=config,
                state=result.state,
                event_type=event_type,
                message=result.message,
                advanced=result.advanced,
                fallback_used=result.fallback_used,
                guardrails=guardrails,
                plan_task_id=plan_task_id,
                interviewer_kit_id=interviewer_kit_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"面试记录持久化失败：{exc}") from exc

    if result.state.completed and getattr(result, "evaluation", None):
        await _persist_interview_report(
            session_id=session_id,
            config=config,
            evaluation=result.evaluation,
            tenant_id=tenant_id,
            user_id=user_id,
        )


async def _persist_interview_report(
    *,
    session_id: str,
    config: InterviewConfig,
    evaluation: dict,
    tenant_id: str,
    user_id: str,
) -> None:
    """会话收尾时把结构化评分卡落库；失败不阻断聊天主流程。"""
    try:
        async with session_scope() as db:
            service = InterviewReportService(db, tenant_id=tenant_id, user_id=user_id)
            await service.persist_evaluation(
                session_id=session_id,
                config=config,
                evaluation=evaluation,
            )
            await safe_evaluate(db, tenant_id=tenant_id, user_id=user_id)
    except Exception:
        logger.exception("interview_report_persist_failed session_id=%s", session_id)


async def _get_or_restore_session(session_id: str, tenant_id: str, user_id: str) -> ApiSession | None:
    session = sessions.get(session_id)
    if session and session.tenant_id == tenant_id and session.user_id == user_id:
        return session
    async with session_scope() as db:
        record = await InterviewPersistenceService(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
        ).get_session_record(session_id)
    if not record:
        return None
    config = InterviewConfig.model_validate(record["config"])
    state = InterviewState.model_validate(record["state"])
    model_id = _resolve_model_id(config.model_id)
    harness = _create_harness(config, offline=False, web_search_enabled=False, model_id=model_id)
    loop = AgentLoop(config, harness)
    loop.set_thread_id(session_id)
    loop.state = state
    restored = ApiSession(
        loop=loop,
        config=config,
        tenant_id=tenant_id,
        user_id=user_id,
        model_id=model_id,
        resume_id=record.get("resume_id"),
        plan_task_id=record.get("plan_task_id"),
        interviewer_kit_id=record.get("interviewer_kit_id"),
    )
    sessions[session_id] = restored
    return restored


def _create_harness(
    config: InterviewConfig,
    *,
    offline: bool,
    web_search_enabled: bool,
    model_id: str,
    thinking_enabled: bool | None = None,
    reasoning_effort: str | None = None,
):
    from interview_agent.core.harness import LangChainInterviewHarness, ScriptedInterviewHarness

    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    runtime = resolve_model_runtime(model_id, codex_config=codex_model_config)
    embedding_client = load_embedding_client_for_existing_vectors(default_vector_path())
    vector_store = load_vector_store_for_run(default_vector_path())
    kb = load_knowledge_base(None, embedding_client=embedding_client, vector_store=vector_store)
    web_search = WebSearchClient() if web_search_enabled else None
    settings = load_settings()
    resolved_thinking_enabled = (
        thinking_enabled
        if thinking_enabled is not None
        else settings.deepseek_thinking_enabled
    )
    resolved_reasoning_effort = reasoning_effort or settings.deepseek_reasoning_effort or "high"
    supported = is_openai_compatible_provider(runtime.provider) or is_supported_native_provider(runtime.provider)
    if offline or not runtime.api_key or not supported:
        return ScriptedInterviewHarness(config, knowledge_base=kb)
    try:
        return LangChainInterviewHarness(
            config,
            knowledge_base=kb,
            web_search=web_search,
            model=runtime.model,
            provider=runtime.provider,
            base_url=runtime.base_url,
            api_key=runtime.api_key,
            wire_api=runtime.wire_api,
            request_timeout=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
            thinking_enabled=resolved_thinking_enabled,
            reasoning_effort=resolved_reasoning_effort,
        )
    except RuntimeError:
        return ScriptedInterviewHarness(config, knowledge_base=kb)


def _check_base64_size(content_base64: str, max_upload_bytes: int) -> None:
    estimated = len(content_base64.encode("utf-8")) * 3 // 4
    if estimated > max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"上传文件过大，最大允许 {max_upload_bytes} 字节。")


def _check_message(message: str, max_chars: int) -> None:
    if len(message.strip()) == 0:
        raise HTTPException(status_code=400, detail="消息不能为空。")
    if len(message) > max_chars:
        raise HTTPException(status_code=413, detail=f"消息过长，最大允许 {max_chars} 个字符。")


def _check_session_request(request: SessionRequest, max_chars: int) -> None:
    values = [
        request.resume_summary,
        request.resume_text,
        request.project_experience,
        request.interview_goal,
    ]
    for value in values:
        if value and len(value) > max_chars:
            raise HTTPException(status_code=413, detail=f"请求内容过长，单字段最大允许 {max_chars} 个字符。")


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()[:64] or "unknown"
    return request.client.host if request.client else "unknown"


def _client_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "")[:256]


def _auth_limit(settings, action: str) -> int:
    if settings.rate_limit_per_minute <= 0:
        return 0
    if action == "login":
        return min(settings.rate_limit_per_minute, 8)
    if action == "register":
        return min(settings.rate_limit_per_minute, 4)
    return min(settings.rate_limit_per_minute, 6)


def _check_auth_rate_limit(request: Request, action: str, subject: str) -> None:
    settings = load_settings()
    limit = _auth_limit(settings, action)
    if limit <= 0:
        return
    ip = _client_ip(request)
    normalized_subject = hashlib.sha256(subject.strip().lower().encode("utf-8")).hexdigest()[:16]
    ip_key = f"auth:{action}:ip:{ip}"
    subject_key = f"auth:{action}:subject:{normalized_subject}"
    if not rate_limiter.check(ip_key, limit) or not rate_limiter.check(subject_key, limit):
        logger.warning(
            json.dumps(
                {
                    "event": "auth_rate_limited",
                    "action": action,
                    "client_ip": ip,
                    "user_agent": _client_user_agent(request),
                    "request_id": _request_id(request),
                },
                ensure_ascii=False,
            )
        )
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")


def _log_access(request: Request, status_code: int, duration_ms: float, request_id: str) -> None:
    level = logging.WARNING if status_code >= 400 else logging.INFO
    logger.log(
        level,
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": _client_ip(request),
                "user_agent": _client_user_agent(request),
            },
            ensure_ascii=False,
        ),
    )


def _response(
    session_id: str,
    result,
    *,
    model_id: str = "",
    usage: UsageResponse | None = None,
) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        message=result.message,
        completed=result.state.completed,
        fallback_used=result.fallback_used,
        guardrails=[finding.message for finding in result.guardrail_findings or []],
        model_id=model_id,
        usage=usage,
        turn_index=len(result.state.turns) or None,
        orchestration=getattr(result, "orchestration", None),
    )


def _resolve_model_id(model_id: str | None) -> str:
    cleaned = (model_id or "").strip()
    if cleaned:
        return cleaned
    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    return codex_model_config.model or DEFAULT_CHAT_MODEL


def _build_subjective_grader() -> tuple[LlmSubjectiveGrader | None, str]:
    """构建主观题 LLM 评分器；离线/无 API key 时返回 (None, model_id) 走关键词降级。"""
    from interview_agent.core.harness import _create_chat_model

    model_id = _resolve_model_id(None)
    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    runtime = resolve_model_runtime(model_id, codex_config=codex_model_config)
    if not runtime.api_key or not is_openai_compatible_provider(runtime.provider):
        return None, model_id
    settings = load_settings()
    try:
        llm = _create_chat_model(
            provider=runtime.provider,
            model=runtime.model,
            base_url=runtime.base_url,
            api_key=runtime.api_key,
            temperature=0.2,
            timeout=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    except RuntimeError:
        return None, model_id
    return LlmSubjectiveGrader(llm, model_id=model_id), model_id


def _build_planner_llm():
    """构建计划生成用 ChatModel；离线/无 API key 时返回 (None, model_id)。"""
    from interview_agent.core.harness import _create_chat_model

    model_id = _resolve_model_id(None)
    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    runtime = resolve_model_runtime(model_id, codex_config=codex_model_config)
    if not runtime.api_key or not is_openai_compatible_provider(runtime.provider):
        return None, model_id
    settings = load_settings()
    try:
        llm = _create_chat_model(
            provider=runtime.provider,
            model=runtime.model,
            base_url=runtime.base_url,
            api_key=runtime.api_key,
            temperature=0.6,
            timeout=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    except RuntimeError:
        return None, model_id
    return llm, model_id


async def _try_generate_llm_plan(db, request: PlanGenerateRequest, context: RequestContext) -> dict | None:
    """尝试 LLM 个性化计划生成；任何失败返回 None 由调用方降级规则模板。"""
    llm, model_id = _build_planner_llm()
    if llm is None:
        return None
    try:
        await _billing_service(db).ensure_can_use(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            model_id=model_id,
        )
    except InsufficientCreditsError:
        return None
    service = PlanGeneratorService(
        db,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        llm=llm,
        model_id=model_id,
    )
    try:
        result = await service.generate(
            title=request.title,
            target_role=request.target_role,
            seniority=request.seniority,
            target_company=request.target_company,
            total_days=request.total_days,
            hours_per_day=request.hours_per_day,
            focus_areas=request.focus_areas,
            resume_id=request.resume_id,
            use_history=request.use_history,
        )
    except Exception:
        logger.exception("LLM plan generation failed")
        return None
    if result is None:
        return None
    try:
        await _billing_service(db).record_generation_usage(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            session_id=None,
            event_type="plan_generate",
            model_id=model_id,
            prompt_text=result.get("prompt_text", "")[:8000],
            response_text=result.get("response_text", "")[:8000],
        )
    except InsufficientCreditsError:
        pass  # 计划已生成，扣费失败不阻断
    return {"plan_id": str(result["plan"].id), "breakdown": result["breakdown"]}


def _compact_dashboard_snapshot(snapshot: dict) -> str:
    streak = snapshot.get("streak") or {}
    today = snapshot.get("today") or {}
    minutes = snapshot.get("study_minutes") or {}
    interviews = snapshot.get("interviews") or {}
    practice = snapshot.get("practice") or {}
    weak = "、".join(item["tag"] for item in (snapshot.get("weak_points") or [])) or "暂无"
    return (
        f"连续打卡 {streak.get('current_streak', 0)} 天（最长 {streak.get('longest_streak', 0)}）；"
        f"今日任务 {today.get('tasks_done', 0)}/{today.get('total_tasks', 0)}；"
        f"本周学习 {minutes.get('week_minutes', 0)} 分钟、累计 {minutes.get('total_minutes', 0)} 分钟；"
        f"模拟面试 {interviews.get('total_reports', 0)} 场、最近评分 {interviews.get('latest_score')}、"
        f"均分 {interviews.get('average_score')}；"
        f"刷题 {practice.get('total_attempts', 0)} 道、正确率 {practice.get('correct_rate', 0)}、"
        f"错题本 {practice.get('wrong_book_count', 0)} 道；薄弱点：{weak}。"
    )


async def _build_dashboard_advice_provider(db, context) -> tuple:
    """构建驾驶舱 LLM 建议闭包；离线/无 key/余额不足时返回 (None, model_id) 走规则文案。"""
    from interview_agent.core.harness import _create_chat_model

    model_id = _resolve_model_id(None)
    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    runtime = resolve_model_runtime(model_id, codex_config=codex_model_config)
    if not runtime.api_key or not is_openai_compatible_provider(runtime.provider):
        return None, model_id
    await _billing_service(db).ensure_can_use(
        tenant_id=context.tenant_id, user_id=context.user_id, model_id=model_id
    )
    settings = load_settings()
    try:
        llm = _create_chat_model(
            provider=runtime.provider,
            model=runtime.model,
            base_url=runtime.base_url,
            api_key=runtime.api_key,
            temperature=0.5,
            timeout=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    except RuntimeError:
        return None, model_id

    async def provider(snapshot: dict) -> dict | None:
        import json as _json

        from langchain_core.messages import HumanMessage, SystemMessage

        response = llm.invoke([
            SystemMessage(content=dashboard_advice_system_prompt()),
            HumanMessage(content=_compact_dashboard_snapshot(snapshot)),
        ])
        raw = getattr(response, "content", response)
        if not isinstance(raw, str):
            raw = str(raw)
        text = raw.strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            payload = _json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict) or not str(payload.get("advice") or "").strip():
            return None
        return {"text": str(payload["advice"]).strip(), "action": str(payload.get("action") or "").strip()}

    return provider, model_id


async def _record_usage(
    *,
    session_id: str,
    event_type: str,
    model_id: str,
    prompt_text: str,
    response_text: str,
    result,
    context: RequestContext,
) -> UsageResponse:
    try:
        async with session_scope() as db:
            charge = await _billing_service(db).record_generation_usage(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=session_id,
                event_type=event_type,
                model_id=model_id,
                prompt_text=prompt_text,
                response_text=response_text,
                usage=getattr(result, "usage", None),
                metadata={"fallback_used": bool(getattr(result, "fallback_used", False))},
                idempotency_key=_usage_idempotency_key(
                    session_id=session_id,
                    event_type=event_type,
                    prompt_text=prompt_text,
                    response_text=response_text,
                    result=result,
                    context=context,
                ),
            )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    return UsageResponse(
        model_id=charge.model.id,
        provider=charge.model.provider,
        input_tokens=charge.usage.input_tokens,
        output_tokens=charge.usage.output_tokens,
        total_tokens=charge.usage.total_tokens,
        cost_credits=str(micros_to_credits(charge.cost_credits_micros)),
        cost_credits_micros=charge.cost_credits_micros,
        trial_used=charge.trial_used,
        trial_uses_remaining=charge.account.trial_uses_remaining,
        credit_balance=str(charge.account.credit_balance),
        credit_balance_micros=charge.account.credit_balance_micros,
    )


def _account_response(snapshot, *, role: str = "user") -> AccountResponse:
    return AccountResponse(
        tenant_id=snapshot.tenant_id,
        user_id=snapshot.user_id,
        display_name=snapshot.display_name,
        email=snapshot.email,
        platform=snapshot.platform,
        role=role,
        trial_uses_remaining=snapshot.trial_uses_remaining,
        credit_balance=str(snapshot.credit_balance),
        credit_balance_micros=snapshot.credit_balance_micros,
        settings=_settings_response(snapshot.settings),
    )


def _settings_response(settings: dict | None) -> UserSettingsResponse:
    raw = dict(settings or {})
    mode = raw.get("default_interview_mode")
    if mode not in {"interviewer", "candidate"}:
        mode = "interviewer"
    return UserSettingsResponse(default_interview_mode=mode)


def _payment_order_response(order) -> PaymentOrderResponse:
    metadata = order.metadata or {}
    return PaymentOrderResponse(
        tenant_id=order.tenant_id,
        user_id=order.user_id,
        amount_credits=str(micros_to_credits(order.amount_micros)),
        amount_micros=order.amount_micros,
        credited_amount=str(micros_to_credits(order.credited_amount_micros)),
        credited_amount_micros=order.credited_amount_micros,
        payment_provider=order.payment_provider,
        external_order_id=order.external_order_id,
        status=order.status,
        created=order.created,
        pay_url=metadata.get("pay_url"),
        code_url=metadata.get("code_url"),
        metadata={
            key: value
            for key, value in metadata.items()
            if key not in {"pay_url", "code_url"}
        },
    )


async def _find_payment_order_for_webhook(db, external_order_id: str):
    if not external_order_id:
        return None
    return await _billing_service(db).find_payment_order_by_external_id(
        external_order_id=external_order_id
    )


def _usage_prompt_text(config: InterviewConfig, request: SessionRequest) -> str:
    payload = {
        "mode": config.mode.value,
        "industry": config.industry.value,
        "candidate": config.candidate.model_dump(mode="json"),
        "focus_areas": config.focus_areas,
        "web_search": request.web_search,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _usage_idempotency_key(
    *,
    session_id: str,
    event_type: str,
    prompt_text: str,
    response_text: str,
    result,
    context: RequestContext,
) -> str:
    request_part = context.request_id or ""
    turn_count = len(getattr(getattr(result, "state", None), "turns", []) or [])
    digest = hashlib.sha256(
        "|".join(
            [
                context.user_id,
                session_id,
                event_type,
                request_part,
                str(turn_count),
                prompt_text,
                response_text,
            ]
        ).encode("utf-8")
    ).hexdigest()[:32]
    request_label = "req" if request_part else "auto"
    return f"usage:{request_label}:{session_id}:{event_type}:{digest}"[:128]


def _billing_service(db) -> BillingService:
    settings = load_settings()
    return BillingService(db, trial_uses=max(settings.trial_uses, 0))


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _generate_plan_description(request: PlanGenerateRequest) -> str:
    parts = [f"目标岗位：{request.target_role or '通用面试'}"]
    if request.seniority:
        parts.append(f"职级：{request.seniority}")
    parts.append(f"复习周期：{request.total_days} 天，日均约 {request.hours_per_day} 小时")
    if request.focus_areas:
        parts.append(f"重点方向：{', '.join(request.focus_areas)}")
    parts.append("规则版自动生成，按 4 阶段拆分，可按需调整。")
    return "；".join(parts)


def _generate_day_title(
    phase_key: str,
    day_in_phase: int,
    phase_total_days: int,
    target_role: str | None,
    focus_areas: list[str] | None,
) -> str:
    role_tag = target_role.strip() if target_role else ""
    if _is_agent_plan(target_role, focus_areas):
        if phase_key == "p1":
            base = ["Agent 岗位定位与项目主线", "大模型基础与上下文工程", "ReAct 循环、工具调用与 MCP"]
        elif phase_key == "p2":
            base = ["RAG、Memory 与知识系统", "Coding Agent：Claude Code / Codex 架构", "Agent 安全、沙箱与权限"]
        elif phase_key == "p3":
            base = ["Agent 评测、观测与线上质量", "生产项目接入与商业化交付", "Agent 系统设计全链路模拟"]
        else:
            base = ["多轮面试高频追问", "最终 A4 速记与全真模拟", "终面表达与状态管理"]
        pick_idx = min(len(base) - 1, (day_in_phase - 1) * len(base) // max(1, phase_total_days))
        return base[pick_idx]
    if phase_key == "p1":
        base = ["简历与自我介绍背诵", "基础素材通读", "简历项目与材料整理"]
    elif phase_key == "p2":
        base = ["项目深挖与 STAR 打磨", "专项技术深入", "公司题库与答题指南"]
    elif phase_key == "p3":
        base = ["全真模拟面试", "错题回顾", "弱点清单二刷"]
    else:
        base = ["A4 速记单整理", "定制公司面复盘", "状态调整与错题回顾"]
    pick_idx = min(len(base) - 1, (day_in_phase - 1) * len(base) // max(1, phase_total_days))
    title = base[pick_idx]
    if (role_tag and "AI" in role_tag) or (focus_areas and any("AI" in f for f in focus_areas)):
        pass
    return title


def _generate_day_tasks(
    *,
    day_key: str,
    phase_key: str,
    day_offset: int,
    phase_days: int,
    target_role: str | None,
    focus_areas: list[str] | None,
) -> list[dict]:
    tasks: list[dict] = []
    focus = set(f.lower() for f in (focus_areas or []))
    if _is_agent_plan(target_role, focus_areas):
        return _generate_agent_day_tasks(
            day_key=day_key,
            phase_key=phase_key,
            day_offset=day_offset,
            phase_days=phase_days,
        )
    if phase_key == "p1":
        tasks.append({"id": f"{day_key}-resume", "title": "简历内容通读并标记数据口径", "tags": ["简历"], "critical": True})
        tasks.append({"id": f"{day_key}-intro", "title": "自我介绍框架梳理，录音 1 遍", "tags": ["开场"], "critical": day_offset == 0})
        tasks.append({"id": f"{day_key}-base", "title": f"基础题库第一轮，第 {day_offset + 1}/{phase_days} 部分", "tags": ["基础"]})
        if any("ai" in f or "rag" in f or "agent" in f for f in focus) or True:
            tasks.append({"id": f"{day_key}-ai", "title": "AI / RAG / Agent 相关素材整理", "tags": ["AI"]})
    elif phase_key == "p2":
        tasks.append({"id": f"{day_key}-star", "title": f"STAR 项目卡打磨，第 {day_offset + 1}/{phase_days} 张", "tags": ["STAR"], "critical": True})
        tasks.append({"id": f"{day_key}-tech", "title": "技术深挖主题阅读并整理要点", "tags": ["深挖"]})
        tasks.append({"id": f"{day_key}-qna", "title": "面试问答过标题并标记弱点清单", "tags": ["问答"]})
        tasks.append({"id": f"{day_key}-wrong", "title": "基础错题抄入错题本", "tags": ["基础"]})
    elif phase_key == "p3":
        tasks.append({"id": f"{day_key}-mock", "title": f"全真模拟 {day_offset + 1}：自我介绍 + 深挖 + 反向提问", "tags": ["模拟"], "simulation": True, "critical": True})
        tasks.append({"id": f"{day_key}-algo", "title": "算法 / 前端高频手写练习", "tags": ["算法"]})
        tasks.append({"id": f"{day_key}-wrong-clear", "title": "错题本回做与整理", "tags": ["错题"], "critical": day_offset == phase_days - 1})
    else:
        tasks.append({"id": f"{day_key}-a4", "title": "A4 速记单整理并过一遍", "tags": ["A4"], "critical": day_offset == 0})
        tasks.append({"id": f"{day_key}-intro", "title": "自我介绍标准版录音一遍", "tags": ["开场"]})
        tasks.append({"id": f"{day_key}-only-wrong", "title": "只刷错题本，不刷新题", "tags": ["错题"], "critical": True})
        tasks.append({"id": f"{day_key}-rest", "title": "早睡 + 状态管理，比刷题更重要", "tags": ["心理"]})
    return tasks


def _is_agent_plan(target_role: str | None, focus_areas: list[str] | None) -> bool:
    text = " ".join([target_role or "", *(focus_areas or [])]).lower()
    return any(key in text for key in ("agent", "ai agent", "coding agent", "大模型", "llm", "ai native", "rag"))


def _generate_agent_day_tasks(
    *,
    day_key: str,
    phase_key: str,
    day_offset: int,
    phase_days: int,
) -> list[dict]:
    topics_by_phase = {
        "p1": [
            (
                "Agent 开发岗位画像、自我介绍与项目证据链",
                "准备 HR 面和技术一面的开场，讲清为什么你能交付 Agent 生产系统。",
                "用 90 秒讲清岗位定位、三条项目证据和一个生产指标。",
            ),
            (
                "大模型基础：Token、Transformer、上下文窗口与结构化输出",
                "补齐 Agent 开发必须解释的大模型底层概念，避免只停留在 API 调用。",
                "能解释 token 成本、上下文污染、结构化输出失败和降级策略。",
            ),
            (
                "ReAct 循环、Tool Calling、MCP 与 Agent Runtime",
                "掌握 Agent 从思考到行动的核心控制流和工具协议。",
                "能画出 Reason-Act-Observe 循环、工具 schema、权限校验和 observation 回填。",
            ),
        ],
        "p2": [
            (
                "RAG 深挖：切分、召回、重排、引用与权限前置过滤",
                "RAG 是 Agent 获取私有事实的核心能力，面试会频繁追问质量和权限。",
                "能设计企业知识库或代码库 RAG，并说明召回、groundedness 和引用指标。",
            ),
            (
                "Memory 与上下文工程：短期记忆、任务轨迹、长期记忆",
                "多轮 Agent 能否稳定依赖上下文分层、摘要和记忆治理。",
                "能说明记忆写入条件、TTL、租户隔离、敏感信息处理和恢复流程。",
            ),
            (
                "Coding Agent 源码学习：Claude Code、Codex CLI、patch 与沙箱",
                "Agent 开发岗位很容易追问真实工具链和源码阅读能力。",
                "能讲清 Coding Agent 从 CLI 输入到读取项目、调用工具、生成 patch、运行测试的链路。",
            ),
            (
                "Agent 安全：Prompt Injection、权限、沙箱、审批与审计",
                "生产 Agent 最大风险来自不可信内容和工具副作用。",
                "能设计工具风险分级、审批、脱敏、审计回放和红队评测样本。",
            ),
        ],
        "p3": [
            (
                "Agent 评测体系：离线回放、LLM-as-Judge、人工抽检与质量门禁",
                "多轮面试会要求你证明 Agent 真的有效，而不是只展示 demo。",
                "能给出 eval case 结构、评分 rubric、上线门禁和线上失败回流机制。",
            ),
            (
                "生产接入：模型网关、任务队列、成本预算、灰度、SLA 与 OnCall",
                "商业化交付必须解释稳定性、成本、安全和可运维性。",
                "能讲清从 MVP 到灰度上线的架构、指标、告警和回滚路径。",
            ),
            (
                "系统设计模拟：从 0 到 1 设计企业 Agent 平台",
                "训练二面/三面的完整架构表达和取舍能力。",
                "能在 20 分钟内完成模块图、数据流、权限流、失败流和指标流说明。",
            ),
            (
                "项目深挖模拟：把个人经历改造成 Agent 岗 STAR 案例",
                "把你的真实经历转成面试官能验证的技术证据。",
                "能回答本人职责、关键决策、失败处理、量化结果和复盘。",
            ),
        ],
        "p4": [
            (
                "Agent 高频追问清单：工具、RAG、Memory、安全、评测、上线",
                "最后阶段集中压缩所有高频题，准备交叉面和主管面。",
                "能连续回答 20 个追问，并把每题压缩到 60-90 秒。",
            ),
            (
                "最终 A4 速记：架构图、指标表、风险表和源码阅读路径",
                "把复习内容压成临场可用的提纲。",
                "能凭一页纸复述 Agent 架构、生产指标、风险和项目证据。",
            ),
            (
                "全真多轮模拟：HR 面、技术面、系统设计面与终面表达",
                "模拟多轮面试节奏，减少临场卡顿。",
                "能完成开场、项目深挖、系统设计、反问和收尾表达。",
            ),
        ],
    }
    topics = topics_by_phase.get(phase_key) or topics_by_phase["p1"]
    topic, reason, acceptance = topics[min(day_offset, len(topics) - 1)]
    return [
        {
            "id": f"{day_key}-study",
            "title": f"复习精讲：{topic}",
            "tags": ["Agent", "复习精讲", phase_key],
            "critical": True,
            "reason": reason,
        },
        {
            "id": f"{day_key}-architecture",
            "title": f"架构拆解：{topic} 的生产落地链路",
            "tags": ["系统设计", "生产化", "Agent"],
            "critical": phase_key in {"p2", "p3"},
            "reason": f"{topic} 需要能落到真实生产项目接入，而不是只会讲概念。",
        },
        {
            "id": f"{day_key}-interview",
            "title": f"面试追问：{topic}",
            "tags": ["多轮面试", "追问", "Agent"],
            "simulation": phase_key in {"p3", "p4"},
            "critical": phase_key in {"p3", "p4"},
            "reason": acceptance,
            "link_type": "interview" if phase_key in {"p3", "p4"} else "none",
            "link_payload": {"mode": "interviewer", "focus": topic} if phase_key in {"p3", "p4"} else {},
        },
    ]


app = create_app()
