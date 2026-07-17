from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from interview_agent.embeddings.embedding import (
    DEFAULT_EMBEDDING_SERVICE_URL,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
)


@dataclass(frozen=True)
class AppSettings:
    environment: str = "development"
    knowledge_base_path: Path = Path("knowledge_base/ai-interview-guide/docs")
    rag_index_path: Path = Path(".interview_agent/rag_index.json")
    rag_vector_path: Path = Path(".interview_agent/rag_vectors.json")
    vector_store_metadata_path: Path = Path(".interview_agent/vector_store.json")
    memory_path: Path = Path(".interview_agent/memory")
    vector_store: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "interview_agent"
    embedding_provider: str = "service"
    embedding_model: str = DEFAULT_LOCAL_EMBEDDING_MODEL
    embedding_service_url: str = DEFAULT_EMBEDDING_SERVICE_URL
    database_url: str = "postgresql+asyncpg://interview_agent:interview_agent@localhost:5432/interview_agent"
    storage_backend: str = "database"
    object_storage_backend: str = "minio"
    object_storage_endpoint: str = "localhost:9002"
    object_storage_access_key: str = "interview_agent"
    object_storage_secret_key: str = "interview_agent_password"
    object_storage_bucket: str = "interview-agent"
    object_storage_secure: bool = False
    api_auth_required: bool = False
    api_tokens: str = ""
    admin_api_tokens: str = ""
    auth_token_secret: str = "dev-secret-change-me"
    auth_token_ttl_seconds: int = 7 * 24 * 60 * 60
    auth_dev_login_enabled: bool = True
    auth_mock_provider_login_enabled: bool = False
    allow_mock_recharge: bool = True
    payment_webhook_secret: str = ""
    public_web_base_url: str = "http://127.0.0.1:5173"
    public_api_base_url: str = "http://127.0.0.1:8020"
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"
    alipay_notify_url: str = ""
    alipay_return_url: str = ""
    wechat_pay_app_id: str = ""
    wechat_pay_mch_id: str = ""
    wechat_pay_api_v3_key: str = ""
    wechat_pay_private_key: str = ""
    wechat_pay_cert_serial_no: str = ""
    wechat_pay_platform_cert_pem: str = ""
    wechat_pay_notify_url: str = ""
    trial_uses: int = 2
    credit_usd_rate: str = "100"
    max_recharge_credits: str = "10000"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_code2session_url: str = "https://api.weixin.qq.com/sns/jscode2session"
    default_tenant_id: str = "default"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_message_chars: int = 8000
    rate_limit_per_minute: int = 60
    store_upload_source_path: bool = False
    rag_top_k: int = 4
    rag_max_chars: int = 6000
    deepseek_thinking_enabled: bool = True
    deepseek_reasoning_effort: str = "high"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}


def load_settings() -> AppSettings:
    return AppSettings(
        environment=os.getenv("INTERVIEW_ENV", os.getenv("APP_ENV", "development")),
        knowledge_base_path=Path(
            os.getenv("INTERVIEW_KNOWLEDGE_BASE", "knowledge_base/ai-interview-guide/docs")
        ),
        rag_index_path=Path(os.getenv("INTERVIEW_RAG_INDEX", ".interview_agent/rag_index.json")),
        rag_vector_path=Path(os.getenv("INTERVIEW_RAG_VECTORS", ".interview_agent/rag_vectors.json")),
        vector_store_metadata_path=Path(
            os.getenv("INTERVIEW_VECTOR_STORE_METADATA", ".interview_agent/vector_store.json")
        ),
        memory_path=Path(os.getenv("INTERVIEW_MEMORY_PATH", ".interview_agent/memory")),
        vector_store=os.getenv("INTERVIEW_VECTOR_STORE", "qdrant"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "interview_agent"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "service"),
        embedding_model=os.getenv("EMBEDDING_MODEL", DEFAULT_LOCAL_EMBEDDING_MODEL),
        embedding_service_url=os.getenv("EMBEDDING_SERVICE_URL", DEFAULT_EMBEDDING_SERVICE_URL),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://interview_agent:interview_agent@localhost:5432/interview_agent",
        ),
        storage_backend=os.getenv("INTERVIEW_STORAGE_BACKEND", "database"),
        object_storage_backend=os.getenv("INTERVIEW_OBJECT_STORAGE_BACKEND", "minio"),
        object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT", "localhost:9002"),
        object_storage_access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY", "interview_agent"),
        object_storage_secret_key=os.getenv(
            "OBJECT_STORAGE_SECRET_KEY", "interview_agent_password"
        ),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", "interview-agent"),
        object_storage_secure=_env_bool("OBJECT_STORAGE_SECURE", False),
        api_auth_required=_env_bool("INTERVIEW_API_AUTH_REQUIRED", False),
        api_tokens=os.getenv("INTERVIEW_API_TOKENS", ""),
        admin_api_tokens=os.getenv("INTERVIEW_ADMIN_API_TOKENS", ""),
        auth_token_secret=os.getenv("INTERVIEW_AUTH_TOKEN_SECRET", "dev-secret-change-me"),
        auth_token_ttl_seconds=int(os.getenv("INTERVIEW_AUTH_TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60))),
        auth_dev_login_enabled=_env_bool("INTERVIEW_AUTH_DEV_LOGIN_ENABLED", True),
        auth_mock_provider_login_enabled=_env_bool("INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED", False),
        allow_mock_recharge=_env_bool("INTERVIEW_ALLOW_MOCK_RECHARGE", True),
        payment_webhook_secret=os.getenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", ""),
        public_web_base_url=os.getenv("PUBLIC_WEB_BASE_URL", "http://127.0.0.1:5173"),
        public_api_base_url=os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8020"),
        alipay_app_id=os.getenv("ALIPAY_APP_ID", ""),
        alipay_private_key=os.getenv("ALIPAY_PRIVATE_KEY", ""),
        alipay_public_key=os.getenv("ALIPAY_PUBLIC_KEY", ""),
        alipay_gateway=os.getenv("ALIPAY_GATEWAY", "https://openapi.alipay.com/gateway.do"),
        alipay_notify_url=os.getenv("ALIPAY_NOTIFY_URL", ""),
        alipay_return_url=os.getenv("ALIPAY_RETURN_URL", ""),
        wechat_pay_app_id=os.getenv("WECHAT_PAY_APP_ID", ""),
        wechat_pay_mch_id=os.getenv("WECHAT_PAY_MCH_ID", ""),
        wechat_pay_api_v3_key=os.getenv("WECHAT_PAY_API_V3_KEY", ""),
        wechat_pay_private_key=os.getenv("WECHAT_PAY_PRIVATE_KEY", ""),
        wechat_pay_cert_serial_no=os.getenv("WECHAT_PAY_CERT_SERIAL_NO", ""),
        wechat_pay_platform_cert_pem=os.getenv("WECHAT_PAY_PLATFORM_CERT_PEM", ""),
        wechat_pay_notify_url=os.getenv("WECHAT_PAY_NOTIFY_URL", ""),
        trial_uses=int(os.getenv("INTERVIEW_TRIAL_USES", "2")),
        credit_usd_rate=os.getenv("INTERVIEW_CREDIT_USD_RATE", "100"),
        max_recharge_credits=os.getenv("INTERVIEW_MAX_RECHARGE_CREDITS", "10000"),
        allowed_origins=os.getenv(
            "INTERVIEW_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ),
        wechat_app_id=os.getenv("WECHAT_MINIAPP_APP_ID", ""),
        wechat_app_secret=os.getenv("WECHAT_MINIAPP_APP_SECRET", ""),
        wechat_code2session_url=os.getenv(
            "WECHAT_CODE2SESSION_URL",
            "https://api.weixin.qq.com/sns/jscode2session",
        ),
        default_tenant_id=os.getenv("INTERVIEW_DEFAULT_TENANT_ID", "default"),
        max_upload_bytes=int(os.getenv("INTERVIEW_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))),
        max_message_chars=int(os.getenv("INTERVIEW_MAX_MESSAGE_CHARS", "8000")),
        rate_limit_per_minute=int(os.getenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "60")),
        store_upload_source_path=_env_bool("INTERVIEW_STORE_UPLOAD_SOURCE_PATH", False),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        rag_max_chars=int(os.getenv("RAG_MAX_CHARS", "6000")),
        deepseek_thinking_enabled=_env_bool("DEEPSEEK_THINKING_ENABLED", True),
        deepseek_reasoning_effort=os.getenv("DEEPSEEK_REASONING_EFFORT", "high"),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
