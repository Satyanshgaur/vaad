from __future__ import annotations

import copy
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from vaad.grammar.tighten import (
    DATE_PATTERN,
    TIME_PATTERN,
    TightenOptions,
    enum_from_description,
    tighten,
)
from vaad.grammar.validate import validate, validate_call


def _props(**fields: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": fields, "required": list(fields)}


@pytest.mark.unit
def test_iso_date_pattern_from_description() -> None:
    schema = _props(when={"type": "string", "description": "Delivery date, YYYY-MM-DD"})
    out = tighten(schema)
    assert out["properties"]["when"]["pattern"] == DATE_PATTERN
    assert "maxLength" not in out["properties"]["when"]


@pytest.mark.unit
def test_loose_date_grammar_leaves_dates_free() -> None:
    schema = _props(when={"type": "string", "description": "Delivery date, YYYY-MM-DD"})
    out = tighten(schema, TightenOptions(date_grammar="loose"))
    assert "pattern" not in out["properties"]["when"]
    assert out["properties"]["when"]["maxLength"] == 512


@pytest.mark.unit
def test_datetime_is_not_given_the_date_pattern() -> None:
    schema = _props(at={"type": "string", "description": "YYYY-MM-DD HH:MM:SS"})
    assert "pattern" not in tighten(schema)["properties"]["at"]


@pytest.mark.unit
def test_time_and_phone_patterns() -> None:
    out = tighten(
        _props(
            t={"type": "string", "description": "24-hour HH:MM"},
            p={"type": "string", "description": "10-digit Indian mobile number"},
        )
    )
    assert out["properties"]["t"]["pattern"] == TIME_PATTERN
    assert out["properties"]["p"]["pattern"] == "^[0-9]{10}$"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Unit, either 'celsius' or 'fahrenheit'", ["celsius", "fahrenheit"]),
        ("Type of ride. One of: 'plus', 'comfort', 'black'", ["plus", "comfort", "black"]),
        ("Location, e.g. 'Berkeley, CA' or 'Paris, France'", None),
        ("The city, for example 'Pune' or 'Delhi'", None),
        ("Defaults to 'celsius'", None),
        ("Must be 'x'", None),
    ],
)
def test_enum_inference_is_conservative(description: str, expected: list[str] | None) -> None:
    assert enum_from_description(description) == expected


@pytest.mark.unit
def test_existing_constraints_are_never_replaced() -> None:
    schema = _props(
        a={"type": "string", "enum": ["x", "y"], "description": "either 'p' or 'q'"},
        b={"type": "string", "pattern": "^z+$", "description": "YYYY-MM-DD"},
        c={"type": "string", "maxLength": 5},
    )
    out = tighten(schema)["properties"]
    assert out["a"]["enum"] == ["x", "y"]
    assert out["b"]["pattern"] == "^z+$"
    assert out["c"]["maxLength"] == 5


@pytest.mark.unit
def test_numbers_stay_numbers_and_structure_is_kept() -> None:
    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "number", "description": "YYYY-MM-DD"},
            "k": {"type": "integer"},
        },
        "required": ["n"],
        "additionalProperties": False,
    }
    out = tighten(schema)
    assert out == schema


@pytest.mark.unit
def test_unsupported_keywords_are_dropped_and_original_untouched() -> None:
    schema = _props(
        xs={"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        n={"type": "number", "multipleOf": 5, "exclusiveMinimum": 0},
    )
    before = copy.deepcopy(schema)
    out = tighten(schema)
    assert schema == before
    assert "uniqueItems" not in out["properties"]["xs"]
    assert out["properties"]["xs"]["items"]["maxLength"] == 512
    assert "multipleOf" not in out["properties"]["n"]
    Draft202012Validator.check_schema(out)


@pytest.mark.unit
def test_tighten_is_idempotent_and_recurses() -> None:
    schema = _props(
        order={
            "type": "object",
            "properties": {"due": {"type": "string", "description": "YYYY-MM-DD"}},
        },
        tags={"type": "array", "items": {"type": "string", "description": "either 'a' or 'b'"}},
    )
    once = tighten(schema)
    assert once["properties"]["order"]["properties"]["due"]["pattern"] == DATE_PATTERN
    assert once["properties"]["tags"]["items"]["enum"] == ["a", "b"]
    assert tighten(once) == once


@pytest.mark.unit
def test_tightened_schema_rejects_what_the_description_forbids() -> None:
    out = tighten(_props(when={"type": "string", "description": "YYYY-MM-DD"}))
    validator = Draft202012Validator(out)
    assert validator.is_valid({"when": "2026-10-25"})
    assert not validator.is_valid({"when": "kal"})
    assert not validator.is_valid({"when": "2026-13-45"})


@pytest.mark.unit
def test_validate_call_flags_unknown_tools_bad_args_and_bad_schemas() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "f", "parameters": _props(n={"type": "number"})},
        },
        {"type": "function", "function": {"name": "broken", "parameters": {"type": "nonsense"}}},
    ]
    assert validate_call("f", {"n": 2}, tools) == []
    assert "unknown tool" in validate_call("g", {}, tools)[0]
    assert validate_call("f", [], tools) == ["<root>: arguments must be a JSON object"]
    assert validate_call("f", {"n": "2"}, tools)[0].startswith("n:")
    assert validate_call("broken", {"x": 1}, tools) == []  # unusable schema never blames the model


@pytest.mark.unit
def test_validate_reports_missing_required() -> None:
    errors = validate({}, _props(n={"type": "number"}))
    assert errors == ["<root>: 'n' is a required property"]
