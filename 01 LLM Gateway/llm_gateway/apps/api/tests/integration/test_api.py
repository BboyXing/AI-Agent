from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from llm_gateway.main import create_app


def _write_config(tmp_path: Path, *, primary_status: int = 200) -> Path:
    path = tmp_path / "gateway.yaml"
    path.write_text(
        f"""
server:
  database_path: "{tmp_path / "gateway.db"}"
identity:
  api_keys: [test-key]
  rate_limit:
    requests: 20
    window_seconds: 60
providers:
  deepseek:
    protocol: openai
    base_url: https://deepseek.test/v1
    api_key: deepseek-key
  openai:
    protocol: openai
    base_url: https://openai.test/v1
    api_key: openai-key
models:
  deepseek-chat:
    provider: deepseek
    model: deepseek-chat
    timeout_seconds: 5
  gpt-main:
    provider: openai
    model: gpt-test
    timeout_seconds: 5
routes:
  default:
    prompt: default
    candidates: [deepseek-chat, gpt-main]
  fast-chat:
    prompt: default
    candidates: [deepseek-chat]
""",
        encoding="utf-8",
    )
    return path


def _upstream_handler(statuses: dict[str, int] | None = None):
    statuses = statuses or {}
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append({"url": str(request.url), "body": body})
        host = request.url.host
        status = statuses.get(host, 200)
        if status >= 400:
            return httpx.Response(status, json={"error": {"message": "upstream rejected"}})
        if body.get("stream"):
            content = (
                'data: {"model":"deepseek-chat","choices":[{"delta":{"role":"assistant"}}]}\n\n'
                'data: {"model":"deepseek-chat","choices":[{"delta":{"content":"streamed"}}]}\n\n'
                'data: {"model":"deepseek-chat","choices":[],"usage":{"prompt_tokens":4,'
                '"completion_tokens":2,"total_tokens":6}}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": f"answer from {host}"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        )

    return handler, calls


def test_chat_completion_and_usage_are_persisted(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, calls = _upstream_handler()
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={"model": "default", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == (
            "answer from deepseek.test"
        )
        assert calls[0]["body"]["model"] == "deepseek-chat"

        usage = client.get(
            "/api/v1/usage/calls",
            headers={"Authorization": "Bearer test-key"},
        )
        assert usage.status_code == 200
        assert usage.json()["total"] == 1
        assert usage.json()["items"][0]["provider"] == "deepseek"


def test_retryable_error_falls_back_to_next_candidate(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, calls = _upstream_handler({"deepseek.test": 500})
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={"model": "default", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "answer from openai.test"
    assert [call["body"]["model"] for call in calls] == ["deepseek-chat", "gpt-test"]


def test_chat_stream_returns_sse_and_completion(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, _ = _upstream_handler()
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"content":"streamed"' in response.text
    assert "data: [DONE]" in response.text


def test_stream_falls_back_before_first_visible_chunk(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, calls = _upstream_handler({"deepseek.test": 500})
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert '"content":"streamed"' in response.text
    assert [call["body"]["model"] for call in calls] == ["deepseek-chat", "gpt-test"]


def test_structured_failure_falls_back_to_next_candidate(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        content = "not-json" if request.url.host == "deepseek.test" else '{"answer":42}'
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    app = create_app(config_path=config, transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "return json"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "answer",
                        "schema": {
                            "type": "object",
                            "properties": {"answer": {"type": "integer"}},
                            "required": ["answer"],
                        },
                    },
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == '{"answer":42}'
    assert calls == ["deepseek.test", "openai.test"]


def test_responses_endpoint_returns_response_object(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, _ = _upstream_handler()
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/responses",
            headers={"Authorization": "Bearer test-key"},
            json={"model": "default", "input": "hello"},
        )

    assert response.status_code == 200
    assert response.json()["object"] == "response"
    assert response.json()["output_text"] == "answer from deepseek.test"


def test_missing_api_key_returns_401(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, _ = _upstream_handler()
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/responses",
            json={"model": "default", "input": "hello"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_non_retryable_upstream_error_does_not_fallback(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    handler, calls = _upstream_handler({"deepseek.test": 400})
    app = create_app(config_path=config, transport=httpx.MockTransport(handler))

    with TestClient(app) as client:
        response = client.post(
            "/v1/responses",
            headers={"Authorization": "Bearer test-key"},
            json={"model": "default", "input": "hello"},
        )

    assert response.status_code == 400
    assert len(calls) == 1
