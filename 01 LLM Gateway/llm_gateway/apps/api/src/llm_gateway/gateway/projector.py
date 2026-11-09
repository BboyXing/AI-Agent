from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from llm_gateway.schemas.gateway import GatewayEvent, GatewayResult


def _usage_dict(usage: object) -> dict[str, int]:
    input_tokens = getattr(usage, "input_tokens", None) or 0
    output_tokens = getattr(usage, "output_tokens", None) or 0
    total_tokens = getattr(usage, "total_tokens", None) or input_tokens + output_tokens
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _response_usage(usage: object) -> dict[str, Any]:
    input_tokens = getattr(usage, "input_tokens", None) or 0
    output_tokens = getattr(usage, "output_tokens", None) or 0
    total_tokens = getattr(usage, "total_tokens", None) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": total_tokens,
    }


def chat_completion_response(
    result: GatewayResult,
    *,
    completion_id: str,
    created: int,
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": result.upstream_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.text},
                "finish_reason": result.finish_reason,
            }
        ],
        "usage": _usage_dict(result.usage),
    }


async def project_chat_stream(
    events: AsyncIterator[GatewayEvent],
    *,
    completion_id: str,
) -> AsyncIterator[str]:
    created = int(time.time())
    first_event = await anext(events)
    model = first_event.upstream_model or "unknown"
    yield _chat_chunk(
        completion_id,
        created,
        model,
        delta={"role": "assistant"},
        finish_reason=None,
    )
    async for event in _prepend(first_event, events):
        if event.upstream_model:
            model = event.upstream_model
        if event.kind == "delta":
            yield _chat_chunk(
                completion_id,
                created,
                model,
                delta={"content": event.text},
                finish_reason=None,
            )
        elif event.kind == "completed":
            yield _chat_chunk(
                completion_id,
                created,
                model,
                delta={},
                finish_reason=event.finish_reason,
                usage=_usage_dict(event.usage),
            )
            yield "data: [DONE]\n\n"
            return
        elif event.kind == "error":
            yield _sse_data(
                {
                    "error": {
                        "message": event.error_message,
                        "type": "upstream_error",
                        "code": event.error_code,
                    }
                }
            )
            yield "data: [DONE]\n\n"
            return


def _chat_chunk(
    completion_id: str,
    created: int,
    model: str,
    *,
    delta: dict[str, Any],
    finish_reason: str | None,
    usage: dict[str, int] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        payload["usage"] = usage
    return _sse_data(payload)


def responses_response(
    result: GatewayResult,
    *,
    response_id: str,
    message_id: str,
    created_at: int,
    instructions: str | None,
    max_output_tokens: int | None,
) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": instructions,
        "max_output_tokens": max_output_tokens,
        "model": result.upstream_model,
        "output": [_response_message(message_id, result.text)],
        "output_text": result.text,
        "parallel_tool_calls": False,
        "temperature": None,
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "usage": _response_usage(result.usage),
        "metadata": {},
    }


async def project_responses_stream(
    events: AsyncIterator[GatewayEvent],
    *,
    response_id: str,
    message_id: str,
    instructions: str | None,
    max_output_tokens: int | None,
) -> AsyncIterator[str]:
    created_at = int(time.time())
    first_event = await anext(events)
    model = first_event.upstream_model or "unknown"
    text_parts: list[str] = []
    usage = None
    output_index = 0
    sequence = 0
    yield _response_event(
        "response.created",
        {
            "type": "response.created",
            "response": _response_shell(
                response_id,
                model,
                created_at,
                instructions,
                max_output_tokens,
                "in_progress",
            ),
            "sequence_number": sequence,
        },
    )
    sequence += 1
    async for event in _prepend(first_event, events):
        if event.upstream_model:
            model = event.upstream_model
        if event.kind == "start":
            yield _response_event(
                "response.output_item.added",
                {
                    "type": "response.output_item.added",
                    "response_id": response_id,
                    "output_index": output_index,
                    "item": {
                        "id": message_id,
                        "type": "message",
                        "status": "in_progress",
                        "role": "assistant",
                        "content": [],
                    },
                    "sequence_number": sequence,
                },
            )
            sequence += 1
            yield _response_event(
                "response.content_part.added",
                {
                    "type": "response.content_part.added",
                    "response_id": response_id,
                    "item_id": message_id,
                    "output_index": output_index,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": "", "annotations": []},
                    "sequence_number": sequence,
                },
            )
            sequence += 1
        elif event.kind == "delta":
            text_parts.append(event.text)
            yield _response_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "response_id": response_id,
                    "item_id": message_id,
                    "output_index": output_index,
                    "content_index": 0,
                    "delta": event.text,
                    "sequence_number": sequence,
                },
            )
            sequence += 1
        elif event.kind == "completed":
            usage = event.usage
            text = "".join(text_parts)
            yield _response_event(
                "response.output_text.done",
                {
                    "type": "response.output_text.done",
                    "response_id": response_id,
                    "item_id": message_id,
                    "output_index": output_index,
                    "content_index": 0,
                    "text": text,
                    "sequence_number": sequence,
                },
            )
            sequence += 1
            result = GatewayResult(
                text=text,
                candidate=event.candidate or "",
                provider=event.provider or "",
                upstream_model=model,
                usage=usage,
                finish_reason=event.finish_reason,
            )
            final = responses_response(
                result,
                response_id=response_id,
                message_id=message_id,
                created_at=created_at,
                instructions=instructions,
                max_output_tokens=max_output_tokens,
            )
            yield _response_event(
                "response.completed",
                {"type": "response.completed", "response": final, "sequence_number": sequence},
            )
            return
        elif event.kind == "error":
            yield _response_event(
                "error",
                {
                    "type": "error",
                    "code": event.error_code,
                    "message": event.error_message,
                    "param": None,
                    "sequence_number": sequence,
                },
            )
            return


def _response_message(message_id: str, text: str) -> dict[str, Any]:
    return {
        "id": message_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def _response_shell(
    response_id: str,
    model: str,
    created_at: int,
    instructions: str | None,
    max_output_tokens: int | None,
    status: str,
) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": status,
        "error": None,
        "incomplete_details": None,
        "instructions": instructions,
        "max_output_tokens": max_output_tokens,
        "model": model,
        "output": [],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": None,
        "metadata": {},
    }


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _response_event(event: str, payload: dict[str, Any]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


async def _prepend(
    first: GatewayEvent,
    rest: AsyncIterator[GatewayEvent],
) -> AsyncIterator[GatewayEvent]:
    yield first
    async for event in rest:
        yield event
