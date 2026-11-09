from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator


class SchemaValidationFailure(ValueError):
    pass


def validate_structured_output(text: str, schema: dict[str, Any] | None) -> None:
    if schema is None:
        return
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationFailure(f"response is not valid JSON: {exc.msg}") from exc
    try:
        Draft202012Validator(schema).validate(payload)
    except Exception as exc:
        raise SchemaValidationFailure(str(exc)) from exc
