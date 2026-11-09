from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

API_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = API_ROOT.parents[1]
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ConfigError(ValueError):
    """Raised when gateway configuration cannot be loaded safely."""


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_path: str = "../../data/gateway.db"


class RateLimitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: int = Field(default=60, ge=1)
    window_seconds: int = Field(default=60, ge=1)


class IdentityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_keys: list[str] = Field(min_length=1)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    @model_validator(mode="after")
    def validate_keys(self) -> IdentityConfig:
        if any(not key.strip() for key in self.api_keys):
            raise ValueError("identity.api_keys cannot contain empty values")
        return self


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["openai", "anthropic"]
    base_url: str = Field(min_length=1)
    api_key: str = ""

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str = Field(min_length=1)
    timeout_seconds: float = Field(default=60, gt=0, le=600)


class RouteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    candidates: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> RouteConfig:
        if len(self.candidates) != len(set(self.candidates)):
            raise ValueError("route candidates must be unique")
        return self


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: ServerConfig = Field(default_factory=ServerConfig)
    identity: IdentityConfig
    providers: dict[str, ProviderConfig] = Field(min_length=1)
    models: dict[str, ModelConfig] = Field(min_length=1)
    routes: dict[str, RouteConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> GatewayConfig:
        for model_name, model in self.models.items():
            if model.provider not in self.providers:
                raise ValueError(
                    f"models.{model_name} references unknown provider {model.provider!r}"
                )
        for route_name, route in self.routes.items():
            for candidate in route.candidates:
                if candidate not in self.models:
                    raise ValueError(
                        f"routes.{route_name} references unknown candidate {candidate!r}"
                    )
        return self

    @property
    def database_file(self) -> Path:
        path = Path(self.server.database_path)
        return path if path.is_absolute() else (API_ROOT / path).resolve()

    @property
    def prompts_dir(self) -> Path:
        return API_ROOT / "prompts"


def _expand_string(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        variable = match.group(1)
        default = match.group(2)
        if variable in os.environ:
            return os.environ[variable]
        if default is not None:
            return default
        raise ConfigError(f"environment variable {variable!r} is required")

    return ENV_PATTERN.sub(replace, value)


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_string(value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def resolve_config_path(config_file: str | Path | None = None) -> Path:
    explicit = config_file if config_file is not None else os.getenv("GATEWAY_CONFIG_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.is_file():
            raise ConfigError(f"gateway config file does not exist: {path}")
        return path
    return API_ROOT / "config" / "gateway.example.yaml"


def load_gateway_config(config_file: str | Path | None = None) -> GatewayConfig:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    load_dotenv(API_ROOT / ".env", override=False)
    path = resolve_config_path(config_file)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"unable to read gateway config: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("gateway config root must be a mapping")
    try:
        return GatewayConfig.model_validate(_expand(raw))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
