from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from llm_gateway.api.deps import IdentityDependency, get_gateway
from llm_gateway.gateway.projector import project_responses_stream, responses_response
from llm_gateway.gateway.service import GatewayService
from llm_gateway.schemas.gateway import CanonicalMessage, GatewayRequest
from llm_gateway.schemas.responses import ResponsesRequest

router = APIRouter(tags=["responses"])


@router.post("/v1/responses", response_model=None)
async def create_response(
    payload: ResponsesRequest,
    request: Request,
    identity: IdentityDependency,
    gateway: Annotated[GatewayService, Depends(get_gateway)],
) -> JSONResponse | StreamingResponse:
    gateway.resolve(payload.model)
    request_id = str(request.state.request_id)
    messages = _messages(payload)
    schema, schema_name = _response_schema(payload)
    gateway_request = GatewayRequest(
        request_id=request_id,
        endpoint="responses",
        route=payload.model,
        messages=messages,
        stream=payload.stream,
        subject=identity.subject,
        temperature=payload.temperature,
        max_tokens=payload.max_output_tokens,
        response_schema=schema,
        response_schema_name=schema_name,
    )
    response_id = f"resp_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"

    if payload.stream:
        events = gateway.stream(gateway_request)
        try:
            first_event = await anext(events)
        except StopAsyncIteration as exc:
            raise RuntimeError("gateway stream ended before producing an event") from exc
        projected = project_responses_stream(
            _chain_first(first_event, events),
            response_id=response_id,
            message_id=message_id,
            instructions=payload.instructions,
            max_output_tokens=payload.max_output_tokens,
        )
        return StreamingResponse(
            projected,
            media_type="text/event-stream",
            headers=_stream_headers(request_id),
        )

    result = await gateway.call_json(gateway_request)
    data = responses_response(
        result,
        response_id=response_id,
        message_id=message_id,
        created_at=int(time.time()),
        instructions=payload.instructions,
        max_output_tokens=payload.max_output_tokens,
    )
    return JSONResponse(data, headers={"X-Request-ID": request_id})


def _messages(payload: ResponsesRequest) -> list[CanonicalMessage]:
    messages: list[CanonicalMessage] = []
    if payload.instructions:
        messages.append(CanonicalMessage(role="system", content=payload.instructions))
    if isinstance(payload.input, str):
        messages.append(CanonicalMessage(role="user", content=payload.input))
        return messages
    for item in payload.input:
        role = "system" if item.role == "developer" else item.role
        if isinstance(item.content, str):
            content = item.content
        else:
            content = "\n".join(part.text for part in item.content)
        messages.append(CanonicalMessage(role=role, content=content))
    return messages


def _response_schema(payload: ResponsesRequest) -> tuple[dict[str, Any] | None, str]:
    if (
        payload.text
        and payload.text.format
        and payload.text.format.type == "json_schema"
        and payload.text.format.schema_
    ):
        return payload.text.format.schema_, payload.text.format.name
    return None, "gateway_response"


def _stream_headers(request_id: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Request-ID": request_id,
    }


async def _chain_first(first: object, rest: object):
    yield first
    async for event in rest:
        yield event
