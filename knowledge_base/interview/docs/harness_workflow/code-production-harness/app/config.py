"""生产环境配置（Pydantic Settings）。所有配置都可通过环境变量覆盖，无代码硬编码。

示例：
  MONGO_URI=mongodb://user:pass@mongo:27017,harness?replicaSet=rs0
  JWT_SECRET=xxx
  LLM_PROXY_BASE_URL=https://litellm.internal/v1
  OIDC_DISCOVERY_URL=https://sso.company.com/.well-known/openid-configuration
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore")

    # --- 基础 ---
    APP_NAME: str = "workflow-harness"
    ENV: str = Field(default="dev", pattern="^(dev|test|staging|prod)$")
    LOG_LEVEL: str = "INFO"

    # --- 数据库 ---
    MONGO_URI: SecretStr = Field(default=SecretStr("mongodb://localhost:27017/harness"))
    MONGO_DB_NAME: str = "harness"
    MONGO_MIN_POOL: int = 5
    MONGO_MAX_POOL: int = 50

    REDIS_URI: str = "redis://localhost:6379/0"

    # --- Kafka/Celery ---
    KAFKA_BROKERS: str = "localhost:9092"
    CELERY_BROKER: str = "redis://localhost:6379/1"      # 小团队 Redis 就够；大团队切 Kafka
    CELERY_BACKEND: str = "redis://localhost:6379/2"

    # --- 安全 ---
    JWT_SECRET: SecretStr = Field(default=SecretStr("CHANGE-ME-IN-PROD"))
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MIN: int = 60 * 8
    # OIDC（公司 SSO），不填则回退本地账号（仅 TEST/DEV）
    OIDC_DISCOVERY_URL: Optional[str] = None
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[SecretStr] = None
    RBAC_POLICY_FILE: str = "app/security/rbac_policy.yml"

    # --- LLM ---
    LLM_DEFAULT_MODEL: str = "openai/gpt-4o-mini"        # litellm 格式
    LLM_FALLBACK_MODELS: list[str] = ["deepseek/deepseek-chat"]
    LLM_PROXY_BASE_URL: Optional[str] = None              # LiteLLM Proxy 地址
    LLM_API_KEY: Optional[SecretStr] = None
    LLM_TIMEOUT: int = 60
    LLM_TEMPERATURE: float = 0.0
    LLM_SEED: int = 42

    # --- Harness 行为 ---
    RUN_MAX_TIMEOUT_SEC: int = 15 * 60                    # 单次 run 15 分钟硬超时
    RUN_MAX_RETRIES: int = 2
    SCENARIO_DEFAULT_PAGE_SIZE: int = 50
    # P0 止血开关
    GATE_ENABLED: bool = True
    DEFERRED_LLM_AS_PASS: bool = False

    # --- OTel ---
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "workflow-harness"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    # --- Prometheus ---
    PROMETHEUS_PORT: int = 9464

    # --- 通知 ---
    SLACK_WEBHOOK_URL: Optional[SecretStr] = None
    FEISHU_WEBHOOK_URL: Optional[SecretStr] = None

    @field_validator("LOG_LEVEL")
    @classmethod
    def _log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
