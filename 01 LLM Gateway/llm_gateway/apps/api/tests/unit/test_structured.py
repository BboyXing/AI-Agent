import pytest

from llm_gateway.gateway.structured import SchemaValidationFailure, validate_structured_output


def test_structured_output_accepts_matching_json() -> None:
    validate_structured_output(
        '{"answer": 42}',
        {
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
        },
    )


def test_structured_output_rejects_invalid_json_and_shape() -> None:
    schema = {"type": "object", "required": ["answer"]}
    with pytest.raises(SchemaValidationFailure):
        validate_structured_output("not-json", schema)
    with pytest.raises(SchemaValidationFailure):
        validate_structured_output("{}", schema)
