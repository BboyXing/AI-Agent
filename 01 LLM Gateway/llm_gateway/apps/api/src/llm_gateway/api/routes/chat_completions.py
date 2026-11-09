from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from llm_gateway.api.deps import IdentityDependency, get_gateway
from llm_gateway.gateway.projector import chat_completion_response, project_chat_stream
from llm_gateway.gateway.service import GatewayService
from llm_gateway.schemas.chat_completions import ChatCompletionRequest, ChatCompletionResponse
from llm_gateway.schemas.gateway import CanonicalMessage, GatewayRequest

router = APIRouter(tags=["chat"])


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        200: {
            "description": "JSON completion or text/event-stream when stream=true",
            "content": {"text/event-stream": {}},
        }
    },
)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    request: Request,
    identity: IdentityDependency,
    gateway: Annotated[GatewayService, Depends(get_gateway)],
) -> ChatCompletionResponse | StreamingResponse | JSONResponse:
    gateway.resolve(payload.model)
    request_id = str(request.state.request_id)
    schema, schema_name = _response_schema(payload)
    gateway_request = GatewayRequest(
        request_id=request_id,
        endpoint="chat.completions",
        route=payload.model,
        messages=[
            CanonicalMessage(role=message.role, content=message.content)
            for message in payload.messages
        ],
        stream=payload.stream,
        subject=identity.subject,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        response_schema=schema,
        response_schema_name=schema_name,
    )

    if payload.stream:
        events = gateway.stream(gateway_request)
        try:
            first_event = await anext(events)
        except StopAsyncIteration as exc:
            raise RuntimeError("gateway stream ended before producing an event") from exc
        projected = project_chat_stream(
            _chain_first(first_event, events),
            completion_id=f"chatcmpl_{uuid.uuid4().hex}",
        )
        return StreamingResponse(
            projected,
            media_type="text/event-stream",
            headers=_stream_headers(request_id),
        )

    result = await gateway.call_json(gateway_request)
    data = chat_completion_response(
        result,
        completion_id=f"chatcmpl_{uuid.uuid4().hex}",
        created=int(time.time()),
    )
    return JSONResponse(data, headers={"X-Request-ID": request_id})


def _response_schema(
    payload: ChatCompletionRequest,
) -> tuple[dict[str, Any] | None, str]:
    response_format = payload.response_format
    if response_format and response_format.type == "json_schema" and response_format.json_schema:
        return response_format.json_schema.schema_, response_format.json_schema.name
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
