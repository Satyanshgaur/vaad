"""Post-generation validation; llama-server silently ignores unsupported schema keywords."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


def validate(args: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return human-readable errors (empty list means valid); fed into the guided retry."""
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(args), key=lambda e: list(map(str, e.path)))
    ]
