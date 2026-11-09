from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True, frozen=True)
class UsageCounts:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True, frozen=True)
class CanonicalMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class GatewayRequest:
    request_id: str
    endpoint: Literal["chat.completions", "responses"]
    route: str
    messages: list[CanonicalMessage]
    stream: bool
    subject: str
    temperature: float | None = None
    max_tokens: int | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str = "gateway_response"


@dataclass(slots=True)
class GatewayResult:
    text: str
    candidate: str
    provider: str
    upstream_model: str
    usage: UsageCounts = field(default_factory=UsageCounts)
    finish_reason: str = "stop"


@dataclass(slots=True)
class GatewayEvent:
    kind: Literal["start", "delta", "completed", "error"]
    sequence: int
    text: str = ""
    candidate: str | None = None
    provider: str | None = None
    upstream_model: str | None = None
    usage: UsageCounts | None = None
    finish_reason: str = "stop"
    error_code: str | None = None
    error_message: str | None = None
