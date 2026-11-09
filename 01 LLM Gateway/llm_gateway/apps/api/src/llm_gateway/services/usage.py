from __future__ import annotations

import uuid
from typing import Any

from llm_gateway.core.logging import trace_log
from llm_gateway.persistence.repository import UsageRepository
from llm_gateway.schemas.gateway import GatewayRequest, UsageCounts


class UsageService:
    def __init__(self, repository: UsageRepository) -> None:
        self.repository = repository

    @staticmethod
    def request_id(candidate: str | None = None) -> str:
        if candidate:
            cleaned = "".join(ch for ch in candidate if ch.isalnum() or ch in "-_")[:36]
            if cleaned:
                return cleaned
        return f"req_{uuid.uuid4().hex}"

    async def begin(self, request: GatewayRequest, prompt: str) -> None:
        await self.repository.start_request(
            request_id=request.request_id,
            endpoint=request.endpoint,
            route=request.route,
            prompt=prompt,
            stream=request.stream,
            subject=request.subject,
        )
        await self.event(request.request_id, "request.started", endpoint=request.endpoint)

    async def begin_attempt(
        self,
        *,
        request_id: str,
        ordinal: int,
        candidate: str,
        provider: str,
        upstream_model: str,
    ) -> int:
        attempt_id = await self.repository.start_attempt(
            request_id=request_id,
            ordinal=ordinal,
            candidate=candidate,
            provider=provider,
            upstream_model=upstream_model,
        )
        await self.event(
            request_id,
            "candidate.started",
            attempt_id,
            candidate=candidate,
            provider=provider,
        )
        return attempt_id

    async def finish_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        latency_ms: int,
        http_status: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        usage: UsageCounts | None = None,
    ) -> None:
        usage = usage or UsageCounts()
        await self.repository.finish_attempt(
            attempt_id,
            status=status,
            latency_ms=latency_ms,
            http_status=http_status,
            error_code=error_code,
            error_message=error_message,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )

    async def finish(
        self,
        request: GatewayRequest,
        *,
        status: str,
        latency_ms: int,
        candidate: str | None = None,
        provider: str | None = None,
        upstream_model: str | None = None,
        usage: UsageCounts | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        usage = usage or UsageCounts()
        await self.repository.finish_request(
            request.request_id,
            status=status,
            selected_candidate=candidate,
            provider=provider,
            upstream_model=upstream_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=latency_ms,
            error_code=error_code,
            error_message=error_message,
        )
        await self.event(
            request.request_id,
            f"request.{status}",
            latency_ms=latency_ms,
            candidate=candidate,
            error_code=error_code,
        )

    async def event(
        self,
        request_id: str,
        event_type: str,
        attempt_id: int | None = None,
        **attributes: Any,
    ) -> None:
        await self.repository.add_trace(
            request_id=request_id,
            attempt_id=attempt_id,
            event_type=event_type,
            attributes=attributes,
        )
        trace_log(event_type, request_id=request_id, attempt_id=attempt_id, **attributes)
