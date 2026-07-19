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
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, Response, StreamingResponse
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
from interview_agent.core.industry import Industry, industry_options
from interview_agent.domain.billing import DEFAULT_CHAT_MODEL, micros_to_credits
from interview_agent.infrastructure.auth_providers import AuthProviderError, exchange_wechat_code
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
from interview_agent.domain.resume import stored_resume_to_payload
from interview_agent.infrastructure.security import (
    RequestContext,
    issue_client_token,
    rate_limiter,
    request_context,
    validate_production_security,
)
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
from interview_agent.services.resume_service import ResumeService


class SessionRequest(BaseModel):
    offline: bool = False
    web_search: bool = False
    mode: str | None = None
    industry: str | None = None
    candidate_name: str | None = None
    target_role: str | None = None
    seniority: str | None = None
    resume_summary: str | None = None
    resume_text: str | None = None
    project_experience: str | None = None
    interview_goal: str | None = None
    focus_areas: list[str] | None = None
    resume_id: str | None = None
    model_id: str | None = None
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = Field(default=None, pattern="^(low|medium|high|max)$")


class MessageRequest(BaseModel):
    message: str


class SessionRewindRequest(BaseModel):
    turn_index: int = Field(..., ge=1)


class DevLoginRequest(BaseModel):
    user_id: str = "dev-user"
    tenant_id: str | None = None
    display_name: str = "本地开发用户"
    platform: str = "dev"


class ProviderLoginRequest(BaseModel):
    code: str
    platform: str | None = None
    tenant_id: str | None = None
    display_name: str | None = None


class PhoneLoginRequest(BaseModel):
    phone: str
    verification_code: str
    tenant_id: str | None = None
    platform: str = "mobile"


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    tenant_id: str
    user_id: str
    platform: str
    display_name: str = ""
    trial_uses_remaining: int = 0
    credit_balance: str = "0"


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = ""
    tenant_id: str | None = None
    platform: str = "web"


class PasswordLoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: str | None = None
    platform: str = "web"


class MeResponse(BaseModel):
    tenant_id: str
    user_id: str
    platform: str
    authenticated: bool
    trial_uses_remaining: int = 0
    credit_balance: str = "0"
    credit_balance_micros: int = 0


class UserSettingsResponse(BaseModel):
    default_interview_mode: str = "interviewer"


class UpdateUserSettingsRequest(BaseModel):
    default_interview_mode: str | None = Field(default=None, pattern="^(interviewer|candidate)$")


class AccountResponse(BaseModel):
    tenant_id: str
    user_id: str
    display_name: str
    email: str | None = None
    platform: str
    trial_uses_remaining: int
    credit_balance: str
    credit_balance_micros: int
    settings: UserSettingsResponse = Field(default_factory=UserSettingsResponse)


class RechargeRequest(BaseModel):
    amount_credits: Decimal = Field(gt=0)
    payment_provider: str = "mock"
    external_order_id: str | None = None
    target_user_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentWebhookPayload(BaseModel):
    tenant_id: str = "default"
    user_id: str
    amount_credits: Decimal = Field(gt=0)
    payment_provider: str = Field(min_length=1, max_length=64)
    external_order_id: str = Field(min_length=1, max_length=128)
    status: str = "paid"
    currency: str = "CREDIT"
    metadata: dict = Field(default_factory=dict)


class CreatePaymentOrderRequest(BaseModel):
    amount_credits: Decimal = Field(gt=0)
    payment_provider: str = Field(min_length=1, max_length=64)
    external_order_id: str | None = Field(default=None, max_length=128)
    metadata: dict = Field(default_factory=dict)


class PaymentOrderResponse(BaseModel):
    tenant_id: str
    user_id: str
    amount_credits: str
    amount_micros: int
    payment_provider: str
    external_order_id: str
    status: str
    created: bool
    pay_url: str | None = None
    code_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentWebhookResponse(BaseModel):
    accepted: bool
    applied: bool
    status: str
    external_order_id: str
    account: AccountResponse | None = None


class ModelOptionResponse(BaseModel):
    id: str
    provider: str
    display_name: str
    category: str = "通用模型"
    runtime_supported: bool = False
    runtime_integration: str = ""
    input_credits_per_1m: str
    output_credits_per_1m: str
    input_usd_per_1m: str
    output_usd_per_1m: str
    context_window: int | None = None
    notes: str = ""


class UsageResponse(BaseModel):
    model_id: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_credits: str
    cost_credits_micros: int
    trial_used: bool
    trial_uses_remaining: int
    credit_balance: str
    credit_balance_micros: int


class ResumeParseRequest(BaseModel):
    filename: str
    content_base64: str


class ResumeParseResponse(BaseModel):
    filename: str
    file_type: str
    text: str
    summary: str
    truncated: bool = False


class ResumeImportRequest(BaseModel):
    filename: str
    content_base64: str
    source_path: str | None = None


class ResumeRecordResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    summary: str
    text: str
    truncated: bool = False
    created_at: str
    updated_at: str
    source_path: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    completed: bool
    fallback_used: bool = False
    guardrails: list[str] = []
    model_id: str = ""
    usage: UsageResponse | None = None
    turn_index: int | None = None


class SessionSummaryResponse(BaseModel):
    id: str
    resume_id: str | None = None
    mode: str
    industry: str
    candidate_name: str
    target_role: str
    seniority: str
    status: str
    created_at: str
    updated_at: str


class SessionDetailResponse(SessionSummaryResponse):
    config: dict
    state: dict
    turns: list[dict]


class DeleteResponse(BaseModel):
    deleted: bool


class IndustryOptionResponse(BaseModel):
    value: str
    label: str
    description: str
    scenario_keywords: list[str]
    interview_focus: list[str]
    production_signals: list[str]
    risk_controls: list[str]
    follow_up_angles: list[str]
    answer_expectations: list[str]
    recommended_focus_areas: list[str]


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


sessions: dict[str, ApiSession] = {}
logger = logging.getLogger("interview_agent.api")


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid4())


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
) -> dict:
    code = error or error_code_for_status(status_code)
    code_value = code.value if isinstance(code, ApiErrorCode) else str(code)
    return {
        "code": status_code,
        "error": code_value,
        "message": message,
        "data": None,
        "request_id": request_id,
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
) -> FastAPI:
    settings = load_settings()
    validate_production_security(settings)
    storage = object_storage or create_object_storage(settings)
    if database_engine is not None:
        configure_database_for_tests(database_engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if initialize_database:
            await init_database()
        await asyncio.to_thread(storage.ensure_ready)
        yield

    app = FastAPI(title="Interview Agent API", lifespan=lifespan)
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
    async def dev_login(request: DevLoginRequest) -> AuthTokenResponse:
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
                    password=request.password,
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
        )

    @app.post("/auth/login", response_model=AuthTokenResponse)
    async def password_login(request: PasswordLoginRequest, http_request: Request) -> AuthTokenResponse:
        _check_auth_rate_limit(http_request, "login", request.email)
        tenant_id = request.tenant_id or settings.default_tenant_id
        async with session_scope() as db:
            account = await _billing_service(db).authenticate_password(
                tenant_id=tenant_id,
                email=request.email,
                password=request.password,
            )
        if account is None:
            raise HTTPException(status_code=401, detail="邮箱或密码错误。")
        return await _issue_auth_response(
            tenant_id=tenant_id,
            user_id=account.user_id,
            platform=request.platform,
            display_name=account.display_name,
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
            )
        if not settings.auth_mock_provider_login_enabled:
            raise HTTPException(status_code=501, detail="微信登录需要接入微信 code2session 后启用。")
        return await _issue_auth_response(
            tenant_id=request.tenant_id or settings.default_tenant_id,
            user_id=f"wechat:{request.code[:32]}",
            platform=request.platform or "miniapp",
            display_name=request.display_name or "微信用户",
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
        )

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
        return _account_response(snapshot)

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
        return _account_response(snapshot)

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
                order = await billing.create_payment_order(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    amount_credits=request.amount_credits,
                    payment_provider=provider,
                    external_order_id=request.external_order_id,
                    metadata={
                        "source": "client_order",
                        "platform": context.platform,
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

    @app.get("/metadata/models", response_model=list[ModelOptionResponse])
    async def models() -> list[ModelOptionResponse]:
        codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
        responses: list[ModelOptionResponse] = []
        for item in list_model_catalog():
            runtime = resolve_model_runtime(item.id, codex_config=codex_model_config)
            runtime_supported = (
                is_openai_compatible_provider(runtime.provider)
                or is_supported_native_provider(runtime.provider)
            )
            responses.append(
                ModelOptionResponse(
                    id=item.id,
                    provider=item.provider,
                    display_name=item.display_name,
                    category=item.category,
                    runtime_supported=runtime_supported,
                    runtime_integration=runtime.integration,
                    input_credits_per_1m=str(item.input_credits_per_1m),
                    output_credits_per_1m=str(item.output_credits_per_1m),
                    input_usd_per_1m=str(item.input_usd_per_1m),
                    output_usd_per_1m=str(item.output_usd_per_1m),
                    context_window=item.context_window,
                    notes=item.notes,
                )
            )
        return responses

    @app.get("/metadata/industries", response_model=list[IndustryOptionResponse])
    async def industries(
        target_role: str = Query(default="AI 应用工程师", min_length=1, max_length=80),
    ) -> list[IndustryOptionResponse]:
        return [IndustryOptionResponse(**item) for item in industry_options(target_role.strip())]

    @app.post("/resume/parse", response_model=ResumeParseResponse)
    async def parse_resume(
        request: ResumeParseRequest,
        context: RequestContext = Depends(request_context),
    ) -> ResumeParseResponse:
        _require_authenticated(context)
        _check_base64_size(request.content_base64, settings.max_upload_bytes)
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
        context: RequestContext = Depends(request_context),
    ) -> ResumeRecordResponse:
        _require_authenticated(context)
        _check_base64_size(request.content_base64, settings.max_upload_bytes)
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
        context: RequestContext = Depends(request_context),
    ) -> list[ResumeRecordResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            resumes = await ResumeService(
                db,
                storage,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list()
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
        await _ensure_resume_access(request.resume_id, storage, context)
        config = apply_session_request(load_config(None), request)
        model_id = _resolve_model_id(request.model_id)
        async with session_scope() as db:
            try:
                await _billing_service(db).ensure_can_use(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    model_id=model_id,
                )
            except InsufficientCreditsError as exc:
                raise HTTPException(status_code=402, detail=str(exc)) from exc
        harness = _create_harness(
            config,
            offline=request.offline,
            web_search_enabled=request.web_search,
            model_id=model_id,
            thinking_enabled=request.thinking_enabled,
            reasoning_effort=request.reasoning_effort,
        )
        loop = AgentLoop(config, harness)
        result = loop.start()
        session_id = str(uuid4())
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
        )
        await _persist_interview_result(
            session_id,
            config,
            result,
            "start",
            request.resume_id,
            context.tenant_id,
            context.user_id,
        )
        return _response(session_id, result, model_id=model_id, usage=usage)

    @app.get("/sessions", response_model=list[SessionSummaryResponse])
    async def list_sessions(
        limit: int = Query(default=50, ge=1, le=200),
        context: RequestContext = Depends(request_context),
    ) -> list[SessionSummaryResponse]:
        _require_authenticated(context)
        async with session_scope() as db:
            records = await InterviewPersistenceService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_sessions(limit=limit)
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

        async def event_stream():
            logger.info(
                "stream_open request_id=%s session_id=%s user_id=%s model_id=%s message_chars=%s",
                request_id,
                session_id,
                context.user_id,
                session.model_id,
                len(message_request.message),
            )
            yield _sse("tool.notice", {"message": "开始分析回答。"})
            previous_state = session.loop.state.model_copy(deep=True)
            llm_started = time.perf_counter()
            logger.info(
                "stream_llm_start request_id=%s session_id=%s model_id=%s turn_count=%s",
                request_id,
                session_id,
                session.model_id,
                len(previous_state.turns),
            )
            try:
                result = session.loop.step(message_request.message)
            except Exception:
                logger.exception(
                    "stream_llm_error request_id=%s session_id=%s model_id=%s duration_ms=%s",
                    request_id,
                    session_id,
                    session.model_id,
                    round((time.perf_counter() - llm_started) * 1000, 2),
                )
                raise
            logger.info(
                "stream_llm_done request_id=%s session_id=%s model_id=%s duration_ms=%s fallback_used=%s completed=%s",
                request_id,
                session_id,
                session.model_id,
                round((time.perf_counter() - llm_started) * 1000, 2),
                result.fallback_used,
                result.state.completed,
            )
            if await http_request.is_disconnected():
                session.loop.state = previous_state
                logger.warning(
                    "stream_client_disconnected request_id=%s session_id=%s model_id=%s rolled_back=true",
                    request_id,
                    session_id,
                    session.model_id,
                )
                return
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
            )
            logger.info(
                "stream_persist_done request_id=%s session_id=%s model_id=%s duration_ms=%s",
                request_id,
                session_id,
                session.model_id,
                round((time.perf_counter() - persist_started) * 1000, 2),
            )
            for finding in result.guardrail_findings or []:
                yield _sse("guardrail.notice", {"message": finding.message})
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
                },
            )
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

    return app


async def _issue_auth_response(
    *,
    tenant_id: str,
    user_id: str,
    platform: str,
    display_name: str,
) -> AuthTokenResponse:
    settings = load_settings()
    try:
        token, expires_at = issue_client_token(
            settings,
            tenant_id=tenant_id,
            user_id=user_id,
            platform=platform,
            display_name=display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    async with session_scope() as db:
        snapshot = await _billing_service(db).account_snapshot(tenant_id=tenant_id, user_id=user_id)
    return AuthTokenResponse(
        access_token=token,
        expires_at=expires_at,
        tenant_id=tenant_id,
        user_id=user_id,
        platform=platform,
        display_name=display_name,
        trial_uses_remaining=snapshot.trial_uses_remaining,
        credit_balance=str(snapshot.credit_balance),
    )


def apply_session_request(config: InterviewConfig, request: SessionRequest) -> InterviewConfig:
    candidate = config.candidate.model_copy(
        update={
            key: value
            for key, value in {
                "name": _clean(request.candidate_name),
                "target_role": _clean(request.target_role),
                "seniority": _clean(request.seniority),
                "resume_summary": _clean(request.resume_summary),
                "resume_text": _clean(request.resume_text),
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
    if context.role == "admin":
        return
    if settings.allow_mock_recharge and not settings.is_production and provider in {"mock", "dev", "manual"}:
        return
    raise HTTPException(status_code=403, detail="充值入账只能由管理员或已签名支付回调完成。")


def _recharge_target_user_id(context: RequestContext, target_user_id: str | None) -> str:
    cleaned = (target_user_id or context.user_id).strip()
    if context.role != "admin" and cleaned != context.user_id:
        raise HTTPException(status_code=403, detail="不能为其他用户充值。")
    if not _valid_subject_id(cleaned):
        raise HTTPException(status_code=400, detail="用户 ID 无效。")
    return cleaned


async def _ensure_resume_access(
    resume_id: str | None,
    storage: ObjectStorage,
    context: RequestContext,
) -> None:
    if not resume_id:
        return
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
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"面试记录持久化失败：{exc}") from exc


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
    loop.state = state
    restored = ApiSession(
        loop=loop,
        config=config,
        tenant_id=tenant_id,
        user_id=user_id,
        model_id=model_id,
        resume_id=record.get("resume_id"),
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
    )


def _resolve_model_id(model_id: str | None) -> str:
    cleaned = (model_id or "").strip()
    if cleaned:
        return cleaned
    codex_model_config = load_codex_model_config(__import__("pathlib").Path.cwd())
    return codex_model_config.model or DEFAULT_CHAT_MODEL


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


def _account_response(snapshot) -> AccountResponse:
    return AccountResponse(
        tenant_id=snapshot.tenant_id,
        user_id=snapshot.user_id,
        display_name=snapshot.display_name,
        email=snapshot.email,
        platform=snapshot.platform,
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


app = create_app()
