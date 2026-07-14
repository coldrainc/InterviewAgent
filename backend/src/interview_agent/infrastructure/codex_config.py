from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class CodexModelConfig:
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    env_key: str | None = None
    wire_api: str | None = None

    @property
    def api_key(self) -> str | None:
        if self.env_key:
            return os.getenv(self.env_key)
        return os.getenv("OPENAI_API_KEY")


def load_codex_model_config(project_root: Path) -> CodexModelConfig:
    """Load the subset of Codex config that is useful for this app's model calls."""

    config: dict[str, Any] = {}

    user_config = _codex_home() / "config.toml"
    _merge(config, _read_toml(user_config))

    project_config = project_root / ".codex" / "config.toml"
    project_values = _read_toml(project_config)
    _merge(config, project_values)

    model = _string_or_none(config.get("model"))
    provider_name = _string_or_none(config.get("model_provider")) or "openai"
    provider = _provider_config(config, provider_name)
    base_url = (
        _string_or_none(provider.get("base_url"))
        or _string_or_none(provider.get("openai_base_url"))
        or _string_or_none(config.get("openai_base_url"))
    )
    env_key = _string_or_none(provider.get("env_key")) or _default_env_key(provider_name, base_url)
    wire_api = _string_or_none(provider.get("wire_api"))
    return CodexModelConfig(
        model=model,
        provider=provider_name,
        base_url=base_url,
        env_key=env_key,
        wire_api=wire_api,
    )


def _codex_home() -> Path:
    return Path(os.getenv("CODEX_HOME", "~/.codex")).expanduser()


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        data = tomllib.load(file)
    return data if isinstance(data, dict) else {}


def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
            continue
        target[key] = value


def _provider_config(config: dict[str, Any], provider_name: str) -> dict[str, Any]:
    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        return {}
    provider = providers.get(provider_name)
    return provider if isinstance(provider, dict) else {}


def _default_env_key(provider_name: str, base_url: str | None) -> str:
    provider = provider_name.lower()
    url = (base_url or "").lower()
    if provider in {"aigw", "gateway"} or "aigateway" in url:
        return "GATEWAY_API_KEY"
    return "OPENAI_API_KEY"


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
