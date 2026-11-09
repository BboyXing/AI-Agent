from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from llm_gateway.core.errors import (
    ProviderUnavailableError,
    StructuredOutputError,
    UpstreamError,
)
from llm_gateway.gateway.adapters.base import ProviderAdapter
from llm_gateway.gateway.router import Candidate, ModelRouter, ResolvedRoute
from llm_gateway.gateway.structured import SchemaValidationFailure, validate_structured_output
from llm_gateway.schemas.gateway import (
    CanonicalMessage,
    GatewayEvent,
    GatewayRequest,
    GatewayResult,
    UsageCounts,
)
from llm_gateway.services.prompts import PromptRegistry
from llm_gateway.services.usage import UsageService


class GatewayService:
    def __init__(
        self,
        *,
        router: ModelRouter,
        prompts: PromptRegistry,
        usage: UsageService,
        adapters: dict[str, ProviderAdapter],
    ) -> None:
        self.router = router
        self.prompts = prompts
        self.usage = usage
        self.adapters = adapters

    def resolve(self, route_name: str) -> ResolvedRoute:
        return self.router.resolve(route_name)

    async def call_json(self, request: GatewayRequest) -> GatewayResult:
        started = time.perf_counter()
        route = self.resolve(request.route)
        prompt = self._prompt(route, request)
        request.messages.insert(0, CanonicalMessage(role="system", content=prompt))
        await self.usage.begin(request, route.prompt)
        last_error: UpstreamError | None = None

        for ordinal, candidate in enumerate(route.candidates, start=1):
            if not candidate.provider.available:
                await self.usage.event(
                    request.request_id,
                    "candidate.skipped",
                    candidate=candidate.name,
                    reason="provider_missing_api_key",
                )
                continue
            adapter = self._adapter(candidate)
            attempt_id = await self.usage.begin_attempt(
                request_id=request.request_id,
                ordinal=ordinal,
                candidate=candidate.name,
                provider=candidate.provider_name,
                upstream_model=candidate.model.model,
            )
            attempt_started = time.perf_counter()
            try:
                result = await adapter.complete(candidate, request)
                if request.response_schema is not None:
                    try:
                        validate_structured_output(result.text, request.response_schema)
                    except SchemaValidationFailure as exc:
                        raise StructuredOutputError(candidate.provider_name, str(exc)) from exc
            except UpstreamError as exc:
                last_error = exc
                latency_ms = _elapsed_ms(attempt_started)
                await self.usage.finish_attempt(
                    attempt_id,
                    status="failed",
                    latency_ms=latency_ms,
                    http_status=exc.status_code,
                    error_code=exc.code,
                    error_message=exc.message,
                )
                await self.usage.event(
                    request.request_id,
                    "candidate.failed",
                    attempt_id,
                    candidate=candidate.name,
                    retryable=exc.retryable,
                    error_code=exc.code,
                )
                if exc.retryable:
                    continue
                await self.usage.finish(
                    request,
                    status="failed",
                    latency_ms=_elapsed_ms(started),
                    error_code=exc.code,
                    error_message=exc.message,
                )
                raise

            latency_ms = _elapsed_ms(attempt_started)
            await self.usage.finish_attempt(
                attempt_id,
                status="success",
                latency_ms=latency_ms,
                usage=result.usage,
            )
            await self.usage.finish(
                request,
                status="success",
                latency_ms=_elapsed_ms(started),
                candidate=result.candidate,
                provider=result.provider,
                upstream_model=result.upstream_model,
                usage=result.usage,
            )
            return result

        message = last_error.message if last_error else "no provider candidate is available"
        error = ProviderUnavailableError(message)
        await self.usage.finish(
            request,
            status="failed",
            latency_ms=_elapsed_ms(started),
            error_code=error.code,
            error_message=error.message,
        )
        raise error

    async def stream(self, request: GatewayRequest) -> AsyncIterator[GatewayEvent]:
        started = time.perf_counter()
        route = self.resolve(request.route)
        prompt = self._prompt(route, request)
        request.messages.insert(0, CanonicalMessage(role="system", content=prompt))
        await self.usage.begin(request, route.prompt)
        sequence = 0
        last_error: UpstreamError | None = None

        for ordinal, candidate in enumerate(route.candidates, start=1):
            if not candidate.provider.available:
                await self.usage.event(
                    request.request_id,
                    "candidate.skipped",
                    candidate=candidate.name,
                    reason="provider_missing_api_key",
                )
                continue
            adapter = self._adapter(candidate)
            attempt_id = await self.usage.begin_attempt(
                request_id=request.request_id,
                ordinal=ordinal,
                candidate=candidate.name,
                provider=candidate.provider_name,
                upstream_model=candidate.model.model,
            )
            attempt_started = time.perf_counter()
            visible = False
            usage = UsageCounts()
            finish_reason = "stop"
            try:
                async for adapter_event in adapter.stream(candidate, request):
                    if adapter_event.usage is not None:
                        usage = adapter_event.usage
                    if adapter_event.kind == "finish":
                        finish_reason = adapter_event.finish_reason
                    if adapter_event.kind == "delta" and adapter_event.text:
                        if not visible:
                            visible = True
                            yield GatewayEvent(
                                kind="start",
                                sequence=sequence,
                                candidate=candidate.name,
                                provider=candidate.provider_name,
                                upstream_model=candidate.model.model,
                            )
                            sequence += 1
                        yield GatewayEvent(
                            kind="delta",
                            sequence=sequence,
                            text=adapter_event.text,
                            candidate=candidate.name,
                            provider=candidate.provider_name,
                            upstream_model=candidate.model.model,
                            finish_reason=finish_reason,
                        )
                        sequence += 1
                if not visible:
                    visible = True
                    yield GatewayEvent(
                        kind="start",
                        sequence=sequence,
                        candidate=candidate.name,
                        provider=candidate.provider_name,
                        upstream_model=candidate.model.model,
                    )
                    sequence += 1
                latency_ms = _elapsed_ms(attempt_started)
                await self.usage.finish_attempt(
                    attempt_id,
                    status="success",
                    latency_ms=latency_ms,
                    usage=usage,
                )
                await self.usage.finish(
                    request,
                    status="success",
                    latency_ms=_elapsed_ms(started),
                    candidate=candidate.name,
                    provider=candidate.provider_name,
                    upstream_model=candidate.model.model,
                    usage=usage,
                )
                yield GatewayEvent(
                    kind="completed",
                    sequence=sequence,
                    candidate=candidate.name,
                    provider=candidate.provider_name,
                    upstream_model=candidate.model.model,
                    usage=usage,
                    finish_reason=finish_reason,
                )
                return
            except asyncio.CancelledError:
                await self.usage.finish_attempt(
                    attempt_id,
                    status="cancelled",
                    latency_ms=_elapsed_ms(attempt_started),
                    usage=usage,
                )
                await self.usage.finish(
                    request,
                    status="cancelled",
                    latency_ms=_elapsed_ms(started),
                    candidate=candidate.name,
                    provider=candidate.provider_name,
                    upstream_model=candidate.model.model,
                    usage=usage,
                    error_code="client_cancelled",
                    error_message="client disconnected",
                )
                raise
            except UpstreamError as exc:
                last_error = exc
                await self.usage.finish_attempt(
                    attempt_id,
                    status="failed",
                    latency_ms=_elapsed_ms(attempt_started),
                    http_status=exc.status_code,
                    error_code=exc.code,
                    error_message=exc.message,
                    usage=usage,
                )
                await self.usage.event(
                    request.request_id,
                    "candidate.failed",
                    attempt_id,
                    candidate=candidate.name,
                    retryable=exc.retryable,
                    error_code=exc.code,
                )
                if not visible and exc.retryable:
                    continue
                await self.usage.finish(
                    request,
                    status="failed",
                    latency_ms=_elapsed_ms(started),
                    candidate=candidate.name if visible else None,
                    provider=candidate.provider_name if visible else None,
                    upstream_model=candidate.model.model if visible else None,
                    usage=usage,
                    error_code=exc.code,
                    error_message=exc.message,
                )
                if not visible:
                    raise
                yield GatewayEvent(
                    kind="error",
                    sequence=sequence,
                    candidate=candidate.name,
                    provider=candidate.provider_name,
                    upstream_model=candidate.model.model,
                    usage=usage,
                    error_code=exc.code,
                    error_message=exc.message,
                )
                return

        message = last_error.message if last_error else "no provider candidate is available"
        error = ProviderUnavailableError(message)
        await self.usage.finish(
            request,
            status="failed",
            latency_ms=_elapsed_ms(started),
            error_code=error.code,
            error_message=error.message,
        )
        raise error

    def _adapter(self, candidate: Candidate) -> ProviderAdapter:
        try:
            return self.adapters[candidate.provider.protocol]
        except KeyError as exc:
            raise ProviderUnavailableError(
                f"no adapter registered for protocol {candidate.provider.protocol!r}"
            ) from exc

    def _prompt(self, route: ResolvedRoute, request: GatewayRequest) -> str:
        prompt = self.prompts.render(
            route.prompt,
            {
                "route": route.name,
                "endpoint": request.endpoint,
                "request_id": request.request_id,
            },
        )
        if request.response_schema is not None:
            prompt += (
                "\nReturn only one JSON value that matches this JSON schema:\n"
                + json.dumps(request.response_schema, ensure_ascii=False)
            )
        return prompt


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
