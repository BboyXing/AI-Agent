from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from llm_gateway.core.errors import UpstreamError
from llm_gateway.gateway.adapters.base import AdapterStreamEvent, ProviderAdapter
from llm_gateway.gateway.router import Candidate
from llm_gateway.schemas.gateway import GatewayRequest, GatewayResult, UsageCounts


class OpenAICompatibleAdapter(ProviderAdapter):
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def complete(self, candidate: Candidate, request: GatewayRequest) -> GatewayResult:
        payload = self._payload(candidate, request, stream=False)
        try:
            response = await self.http.post(
                self._endpoint(candidate),
                headers=self._headers(candidate, stream=False),
                json=payload,
                timeout=candidate.model.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise self._transport_error(candidate, exc) from exc
        self._raise_upstream(candidate, response)
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise UpstreamError(
                "provider returned an unexpected completion payload",
                provider=candidate.provider_name,
                retryable=True,
                code="invalid_upstream_payload",
            ) from exc
        usage = self._usage(data.get("usage"))
        return GatewayResult(
            text=text,
            candidate=candidate.name,
            provider=candidate.provider_name,
            upstream_model=candidate.model.model,
            usage=usage,
            finish_reason=choice.get("finish_reason") or "stop",
        )

    async def stream(
        self,
        candidate: Candidate,
        request: GatewayRequest,
    ) -> AsyncIterator[AdapterStreamEvent]:
        payload = self._payload(candidate, request, stream=True)
        try:
            async with self.http.stream(
                "POST",
                self._endpoint(candidate),
                headers=self._headers(candidate, stream=True),
                json=payload,
                timeout=candidate.model.timeout_seconds,
            ) as response:
                self._raise_upstream(candidate, response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    value = line[5:].strip()
                    if not value:
                        continue
                    if value == "[DONE]":
                        break
                    try:
                        chunk = json.loads(value)
                    except json.JSONDecodeError as exc:
                        raise UpstreamError(
                            "provider sent malformed stream data",
                            provider=candidate.provider_name,
                            retryable=True,
                            code="invalid_stream_payload",
                        ) from exc
                    if "error" in chunk:
                        error = chunk["error"]
                        raise UpstreamError(
                            str(error.get("message", "provider stream error")),
                            provider=candidate.provider_name,
                            retryable=True,
                            code=str(error.get("code", "provider_stream_error")),
                        )
                    usage = self._usage(chunk.get("usage"))
                    if usage.total_tokens is not None:
                        yield AdapterStreamEvent(kind="usage", usage=usage)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield AdapterStreamEvent(kind="delta", text=text)
                    if choice.get("finish_reason"):
                        yield AdapterStreamEvent(
                            kind="finish",
                            finish_reason=choice["finish_reason"],
                        )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise self._transport_error(candidate, exc) from exc

    def _payload(
        self,
        candidate: Candidate,
        request: GatewayRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": candidate.model.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _endpoint(self, candidate: Candidate) -> str:
        return f"{candidate.provider.base_url.rstrip('/')}/chat/completions"

    def _headers(self, candidate: Candidate, *, stream: bool) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {candidate.provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }

    @staticmethod
    def _usage(raw: dict[str, Any] | None) -> UsageCounts:
        if not isinstance(raw, dict):
            return UsageCounts()
        input_tokens = raw.get("prompt_tokens", raw.get("input_tokens"))
        output_tokens = raw.get("completion_tokens", raw.get("output_tokens"))
        total_tokens = raw.get("total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return UsageCounts(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

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
            code = error.get("code", code) or code
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
