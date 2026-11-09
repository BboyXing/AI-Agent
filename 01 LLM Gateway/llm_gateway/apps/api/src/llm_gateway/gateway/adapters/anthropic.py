from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from llm_gateway.core.errors import UpstreamError
from llm_gateway.gateway.adapters.base import AdapterStreamEvent, ProviderAdapter
from llm_gateway.gateway.router import Candidate
from llm_gateway.schemas.gateway import GatewayRequest, GatewayResult, UsageCounts


class AnthropicAdapter(ProviderAdapter):
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def complete(self, candidate: Candidate, request: GatewayRequest) -> GatewayResult:
        try:
            response = await self.http.post(
                self._endpoint(candidate),
                headers=self._headers(candidate),
                json=self._payload(candidate, request, stream=False),
                timeout=candidate.model.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise self._transport_error(candidate, exc) from exc
        self._raise_upstream(candidate, response)
        try:
            data = response.json()
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        except (ValueError, TypeError) as exc:
            raise UpstreamError(
                "provider returned an unexpected messages payload",
                provider=candidate.provider_name,
                retryable=True,
                code="invalid_upstream_payload",
            ) from exc
        return GatewayResult(
            text=text,
            candidate=candidate.name,
            provider=candidate.provider_name,
            upstream_model=candidate.model.model,
            usage=self._usage(data.get("usage")),
            finish_reason=self._finish_reason(data.get("stop_reason")),
        )

    async def stream(
        self,
        candidate: Candidate,
        request: GatewayRequest,
    ) -> AsyncIterator[AdapterStreamEvent]:
        input_tokens: int | None = None
        output_tokens: int | None = None
        finish_reason = "stop"
        try:
            async with self.http.stream(
                "POST",
                self._endpoint(candidate),
                headers=self._headers(candidate),
                json=self._payload(candidate, request, stream=True),
                timeout=candidate.model.timeout_seconds,
            ) as response:
                self._raise_upstream(candidate, response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    value = line[5:].strip()
                    if not value:
                        continue
                    try:
                        event = json.loads(value)
                    except json.JSONDecodeError as exc:
                        raise UpstreamError(
                            "provider sent malformed stream data",
                            provider=candidate.provider_name,
                            retryable=True,
                            code="invalid_stream_payload",
                        ) from exc
                    event_type = event.get("type")
                    if event_type == "error":
                        error = event.get("error", {})
                        raise UpstreamError(
                            str(error.get("message", "provider stream error")),
                            provider=candidate.provider_name,
                            retryable=True,
                            code=str(error.get("type", "provider_stream_error")),
                        )
                    if event_type == "message_start":
                        usage = event.get("message", {}).get("usage", {})
                        input_tokens = usage.get("input_tokens", input_tokens)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield AdapterStreamEvent(kind="delta", text=delta["text"])
                    elif event_type == "message_delta":
                        usage = event.get("usage", {})
                        output_tokens = usage.get("output_tokens", output_tokens)
                        finish_reason = self._finish_reason(
                            event.get("delta", {}).get("stop_reason")
                        )
                    elif event_type == "message_stop":
                        total = (
                            (input_tokens or 0) + (output_tokens or 0)
                            if input_tokens is not None or output_tokens is not None
                            else None
                        )
                        if total is not None:
                            yield AdapterStreamEvent(
                                kind="usage",
                                usage=UsageCounts(
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    total_tokens=total,
                                ),
                            )
                        yield AdapterStreamEvent(kind="finish", finish_reason=finish_reason)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise self._transport_error(candidate, exc) from exc

    def _payload(
        self,
        candidate: Candidate,
        request: GatewayRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        system_messages = [
            message.content for message in request.messages if message.role == "system"
        ]
        payload: dict[str, Any] = {
            "model": candidate.model.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
                if message.role != "system"
            ],
            "stream": stream,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        return payload

    def _endpoint(self, candidate: Candidate) -> str:
        base = candidate.provider.base_url.rstrip("/")
        return f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

    def _headers(self, candidate: Candidate) -> dict[str, str]:
        return {
            "x-api-key": candidate.provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    @staticmethod
    def _usage(raw: dict[str, Any] | None) -> UsageCounts:
        if not isinstance(raw, dict):
            return UsageCounts()
        input_tokens = raw.get("input_tokens")
        output_tokens = raw.get("output_tokens")
        total = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        return UsageCounts(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
        )

    @staticmethod
    def _finish_reason(value: str | None) -> str:
        return {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }.get(value or "", value or "stop")

    @staticmethod
    def _transport_error(candidate: Candidate, exc: Exception) -> UpstreamError:
        code = "upstream_timeout" if isinstance(exc, httpx.TimeoutException) else "upstream_network"
        return UpstreamError(
            f"provider request failed: {type(exc).__name__}",
            provider=candidate.provider_name,
            retryable=True,
            status_code=504 if code == "upstream_timeout" else 502,
            code=code,
        )

    @staticmethod
    def _raise_upstream(candidate: Candidate, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        message = response.reason_phrase
        code = "upstream_http_error"
        try:
            payload = response.json()
            error = payload.get("error", payload)
            message = error.get("message", message)
            code = error.get("type", code) or code
        except (ValueError, AttributeError):
            message = response.text[:500] or message
        retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
        raise UpstreamError(
            str(message),
            provider=candidate.provider_name,
            retryable=retryable,
            status_code=response.status_code,
            code=str(code),
        )
