from interview_agent.domain.billing import DEFAULT_CHAT_MODEL, default_model_catalog, get_model_pricing
from interview_agent.infrastructure.codex_config import CodexModelConfig
from interview_agent.infrastructure.model_runtime import (
    is_openai_compatible_provider,
    is_supported_native_provider,
    resolve_model_runtime,
)


def test_default_model_catalog_contains_current_provider_models() -> None:
    catalog = default_model_catalog()

    for model_id in (
        "gpt-5.5",
        "gpt-5.5-pro",
        "claude-fable-5",
        "gemini-3.5-flash",
        "deepseek-v4-pro",
        "qwen3.7-max",
        "kimi-k2.7-code",
        "grok-4.3",
    ):
        assert model_id in catalog

    assert get_model_pricing("").id == DEFAULT_CHAT_MODEL


def test_public_model_catalog_is_curated() -> None:
    visible = {model_id for model_id, model in default_model_catalog().items() if model.enabled}

    assert visible == {
        "gpt-5.5",
        "gpt-5.5-pro",
        "gpt-5.4-mini",
        "claude-fable-5",
        "gemini-3.5-flash",
        "deepseek-v4-pro",
        "qwen3.7-max",
        "kimi-k2.7-code",
    }


def test_google_runtime_uses_openai_compatible_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")

    runtime = resolve_model_runtime("gemini-3.5-flash", codex_config=CodexModelConfig())

    assert runtime.provider == "google"
    assert runtime.api_key == "gemini-secret"
    assert runtime.api_key_env == "GEMINI_API_KEY"
    assert runtime.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert runtime.integration == "openai-compatible"
    assert is_openai_compatible_provider(runtime.provider)


def test_anthropic_runtime_uses_native_langchain_provider(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")

    runtime = resolve_model_runtime("claude-fable-5", codex_config=CodexModelConfig())

    assert runtime.provider == "anthropic"
    assert runtime.api_key == "anthropic-secret"
    assert runtime.integration == "native-langchain"
    assert is_supported_native_provider(runtime.provider)


def test_provider_specific_model_does_not_reuse_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    runtime = resolve_model_runtime("deepseek-chat", codex_config=CodexModelConfig())

    assert runtime.provider == "deepseek"
    assert runtime.api_key is None


def test_codex_gateway_can_route_non_openai_provider(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_API_KEY", "gateway-secret")

    runtime = resolve_model_runtime(
        "deepseek-chat",
        codex_config=CodexModelConfig(
            provider="AIGW",
            base_url="https://aigateway.example/v1",
            env_key="GATEWAY_API_KEY",
        ),
    )

    assert runtime.provider == "deepseek"
    assert runtime.api_key == "gateway-secret"
    assert runtime.base_url == "https://aigateway.example/v1"
