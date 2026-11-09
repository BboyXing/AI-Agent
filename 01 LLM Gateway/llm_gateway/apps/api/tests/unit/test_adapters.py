from __future__ import annotations

import json

import httpx
import pytest

from llm_gateway.gateway.adapters.anthropic import AnthropicAdapter
from llm_gateway.gateway.adapters.openai import OpenAICompatibleAdapter
from llm_gateway.gateway.router import ModelRouter
from llm_gateway.schemas.gateway import CanonicalMessage, GatewayRequest


@pytest.mark.asyncio
async def test_openai_adapter_uses_deepseek_chat_model(test_config) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 2,
                    "total_tokens": 10,
                },
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(http)
    candidate = ModelRouter(test_config).resolve("default").candidates[0]
    result = await adapter.complete(
        candidate,
        GatewayRequest(
            request_id="req_test",
            endpoint="chat.completions",
            route="default",
            messages=[CanonicalMessage(role="user", content="hi")],
            stream=False,
            subject="test",
        ),
    )

    assert captured["url"] == "https://deepseek.test/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek-chat"
    assert result.text == "hello"
    assert result.usage.total_tokens == 10
    await http.aclose()


@pytest.mark.asyncio
async def test_anthropic_adapter_extracts_system_and_usage(test_config) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "reviewed"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AnthropicAdapter(http)
    # Resolve directly to keep this test independent from route ordering.
    from llm_gateway.gateway.router import Candidate

    model = test_config.models["claude-main"]
    provider = test_config.providers["anthropic"]
    candidate = Candidate(
        name="claude-main",
        model=model,
        provider_name="anthropic",
        provider=provider,
    )
    result = await adapter.complete(
        candidate,
        GatewayRequest(
            request_id="req_test",
            endpoint="responses",
            route="default",
            messages=[
                CanonicalMessage(role="system", content="system"),
                CanonicalMessage(role="user", content="hi"),
            ],
            stream=False,
            subject="test",
        ),
    )

    assert captured["body"]["system"] == "system"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert result.usage.total_tokens == 15
    await http.aclose()
