from __future__ import annotations

import os
from dataclasses import dataclass

from interview_agent.domain.billing import get_model_pricing
from interview_agent.infrastructure.codex_config import CodexModelConfig


@dataclass(frozen=True)
class ModelRuntimeConfig:
    model: str
    provider: str
    base_url: str | None
    api_key: str | None
    wire_api: str | None = None
    integration: str = "openai-compatible"
    api_key_env: str | None = None


OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "google",
    "deepseek",
    "alibaba",
    "volcengine",
    "moonshot",
    "xai",
    "custom",
}

NATIVE_LANGCHAIN_PROVIDERS = {
    "anthropic",
}


def resolve_model_runtime(
    model_id: str,
    *,
    codex_config: CodexModelConfig,
) -> ModelRuntimeConfig:
    pricing = get_model_pricing(model_id)
    provider = pricing.provider
    provider_runtime = _provider_runtime(provider)
    codex_provider = (codex_config.provider or "").lower()
    has_codex_gateway = bool(codex_config.base_url or codex_provider in {"aigw", "gateway", "custom"})
    if provider in {"openai", "custom"}:
        api_key = (
            provider_runtime.api_key
            or codex_config.api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GATEWAY_API_KEY")
        )
        base_url = provider_runtime.base_url or codex_config.base_url
    elif provider_runtime.api_key:
        api_key = provider_runtime.api_key
        base_url = provider_runtime.base_url
    elif has_codex_gateway:
        api_key = codex_config.api_key or os.getenv("GATEWAY_API_KEY")
        base_url = codex_config.base_url or provider_runtime.base_url
    else:
        api_key = None
        base_url = provider_runtime.base_url
    return ModelRuntimeConfig(
        model=model_id,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        wire_api=codex_config.wire_api,
        integration=provider_runtime.integration,
        api_key_env=provider_runtime.api_key_env,
    )


def is_openai_compatible_provider(provider: str) -> bool:
    return provider in OPENAI_COMPATIBLE_PROVIDERS


def is_supported_native_provider(provider: str) -> bool:
    return provider in NATIVE_LANGCHAIN_PROVIDERS


def _provider_runtime(provider: str) -> ModelRuntimeConfig:
    mapping = {
        "openai": (None, ("OPENAI_API_KEY",), "openai-compatible"),
        "anthropic": (None, ("ANTHROPIC_API_KEY",), "native-langchain"),
        "google": (
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            "openai-compatible",
        ),
        "deepseek": ("https://api.deepseek.com/v1", ("DEEPSEEK_API_KEY",), "openai-compatible"),
        "alibaba": (
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ("DASHSCOPE_API_KEY",),
            "openai-compatible",
        ),
        "volcengine": (
            "https://ark.cn-beijing.volces.com/api/v3",
            ("ARK_API_KEY",),
            "openai-compatible",
        ),
        "moonshot": ("https://api.moonshot.cn/v1", ("MOONSHOT_API_KEY",), "openai-compatible"),
        "xai": ("https://api.x.ai/v1", ("XAI_API_KEY",), "openai-compatible"),
    }
    base_url, env_keys, integration = mapping.get(provider, (None, ("OPENAI_API_KEY",), "openai-compatible"))
    api_key_env, api_key = _first_env(env_keys)
    return ModelRuntimeConfig(
        model="",
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        integration=integration,
        api_key_env=api_key_env,
    )


def _first_env(env_keys: tuple[str, ...]) -> tuple[str | None, str | None]:
    for key in env_keys:
        value = os.getenv(key)
        if value:
            return key, value
    return (env_keys[0] if env_keys else None), None
