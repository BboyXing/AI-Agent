from __future__ import annotations

from pathlib import Path

import pytest

from llm_gateway.core.config import GatewayConfig


@pytest.fixture
def test_config(tmp_path: Path) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "server": {
                "cors_origins": ["http://localhost:5173"],
                "database_path": str(tmp_path / "gateway.db"),
            },
            "identity": {
                "api_keys": ["test-key"],
                "rate_limit": {"requests": 50, "window_seconds": 60},
            },
            "providers": {
                "deepseek": {
                    "protocol": "openai",
                    "base_url": "https://deepseek.test/v1",
                    "api_key": "deepseek-key",
                },
                "openai": {
                    "protocol": "openai",
                    "base_url": "https://openai.test/v1",
                    "api_key": "openai-key",
                },
                "anthropic": {
                    "protocol": "anthropic",
                    "base_url": "https://anthropic.test",
                    "api_key": "anthropic-key",
                },
            },
            "models": {
                "deepseek-chat": {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "timeout_seconds": 5,
                },
                "gpt-main": {
                    "provider": "openai",
                    "model": "gpt-test",
                    "timeout_seconds": 5,
                },
                "claude-main": {
                    "provider": "anthropic",
                    "model": "claude-test",
                    "timeout_seconds": 5,
                },
            },
            "routes": {
                "default": {
                    "prompt": "default",
                    "candidates": ["deepseek-chat", "gpt-main"],
                },
                "fast-chat": {
                    "prompt": "code_review",
                    "candidates": ["deepseek-chat"],
                },
            },
        }
    )
