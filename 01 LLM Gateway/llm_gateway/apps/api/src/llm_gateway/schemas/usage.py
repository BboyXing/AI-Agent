from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ModelCandidateInfo(BaseModel):
    id: str
    provider: str
    model: str
    available: bool


class ModelRouteInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "llm-gateway"
    prompt: str
    candidates: list[ModelCandidateInfo]


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelRouteInfo]


class UsageSummary(BaseModel):
    request_count: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    success_rate: float
    average_latency_ms: float


class AttemptRecord(BaseModel):
    id: int
    ordinal: int
    candidate: str
    provider: str
    upstream_model: str
    status: str
    http_status: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    started_at: str
    completed_at: str | None = None


class TraceRecord(BaseModel):
    event_type: str
    created_at: str
    attributes: dict[str, object]


class CallRecord(BaseModel):
    request_id: str
    endpoint: str
    route: str
    prompt: str
    stream: bool
    subject: str
    status: str
    selected_candidate: str | None = None
    provider: str | None = None
    upstream_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None


class CallDetail(CallRecord):
    attempts: list[AttemptRecord]
    trace: list[TraceRecord]


class CallPage(BaseModel):
    items: list[CallRecord]
    total: int
    limit: int
    offset: int
