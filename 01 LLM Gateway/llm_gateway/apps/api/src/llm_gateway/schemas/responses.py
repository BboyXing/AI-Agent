from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResponseContentPart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["input_text", "output_text", "text"]
    text: str


class ResponseInputMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "developer", "user", "assistant"]
    content: str | list[ResponseContentPart]


class ResponseTextFormat(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["text", "json_object", "json_schema"]
    name: str = "gateway_response"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    strict: bool = True


class ResponseTextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ResponseTextFormat | None = None


class ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    input: str | list[ResponseInputMessage]
    instructions: str | None = None
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1)
    text: ResponseTextConfig | None = None

    @model_validator(mode="after")
    def reject_streaming_schema(self) -> ResponsesRequest:
        if (
            self.stream
            and self.text
            and self.text.format
            and self.text.format.type == "json_schema"
        ):
            raise ValueError("streaming responses do not support json_schema validation")
        return self
