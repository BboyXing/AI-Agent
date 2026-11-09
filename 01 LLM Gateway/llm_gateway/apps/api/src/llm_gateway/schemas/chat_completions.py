from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class JsonSchemaDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = "gateway_response"
    schema_: dict[str, Any] = Field(alias="schema")
    strict: bool = True


class ChatResponseFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "json_object", "json_schema"]
    json_schema: JsonSchemaDefinition | None = None

    @model_validator(mode="after")
    def validate_json_schema(self) -> ChatResponseFormat:
        if self.type == "json_schema" and self.json_schema is None:
            raise ValueError("json_schema response_format requires json_schema")
        return self


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    response_format: ChatResponseFormat | None = None

    @model_validator(mode="after")
    def reject_streaming_schema(self) -> ChatCompletionRequest:
        if self.stream and self.response_format and self.response_format.type == "json_schema":
            raise ValueError("streaming chat completions do not support json_schema validation")
        return self


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage
