from __future__ import annotations

from pathlib import Path

import pytest

from llm_gateway.core.config import ConfigError, load_gateway_config


def test_config_expands_environment_and_preserves_deepseek_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_KEY", "secret")
    monkeypatch.setenv("DB_FILE", str(tmp_path / "usage.db"))
    path = tmp_path / "gateway.yaml"
    path.write_text(
        """
server:
  database_path: "${DB_FILE}"
identity:
  api_keys: ["${GATEWAY_KEY:-test-key}"]
providers:
  deepseek:
    protocol: openai
    base_url: "https://api.deepseek.com/v1"
    api_key: "${DEEPSEEK_KEY}"
models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
routes:
  default:
    prompt: default
    candidates: [deepseek-chat]
""",
        encoding="utf-8",
    )

    config = load_gateway_config(path)

    assert config.providers["deepseek"].api_key == "secret"
    assert config.models["deepseek-chat"].model == "deepseek-chat"
    assert config.routes["default"].candidates == ["deepseek-chat"]


def test_missing_explicit_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_gateway_config(tmp_path / "missing.yaml")


def test_unknown_route_candidate_fails(tmp_path: Path) -> None:
    path = tmp_path / "gateway.yaml"
    path.write_text(
        """
identity:
  api_keys: [test-key]
providers:
  deepseek:
    protocol: openai
    base_url: https://api.deepseek.com/v1
    api_key: test
models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
routes:
  default:
    prompt: default
    candidates: [missing-model]
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown candidate"):
        load_gateway_config(path)
