"""Post-generation validation; llama-server silently ignores unsupported schema keywords."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, UnknownType


def validate(args: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return human-readable errors (empty list means valid); fed into the guided retry.

    A schema that is itself invalid JSON Schema (some BFCL ones are) cannot be checked, so it
    never counts against the model.
    """
    try:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(args), key=lambda e: list(map(str, e.path)))
    except (SchemaError, UnknownType):
        return []
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]


def validate_call(name: str, arguments: Any, tools: list[dict[str, Any]]) -> list[str]:
    """Errors for one tool call against the offered ``tools`` (OpenAI function format)."""
    schemas = {t["function"]["name"]: t["function"].get("parameters", {}) for t in tools}
    if name not in schemas:
        return [f"unknown tool {name!r}; the available tools are {sorted(schemas)}"]
    if not isinstance(arguments, dict):
        return ["<root>: arguments must be a JSON object"]
    return validate(arguments, schemas[name])
