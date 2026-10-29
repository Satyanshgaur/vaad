"""Tighten tool schemas so llama-server's JSON-schema grammar constrains more.

llama-server turns the tool's ``parameters`` schema into a grammar and silently ignores the
keywords it does not support, so this module (a) adds the constraints it does support when the
schema's own description makes them unambiguous, and (b) drops the keywords that would be
ignored anyway. The original schema is kept for validation after generation.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Literal

# Keywords llama.cpp's schema-to-grammar converter does not implement.
UNSUPPORTED = frozenset(
    {
        "uniqueItems",
        "multipleOf",
        "not",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
        "dependencies",
        "contains",
        "minContains",
        "maxContains",
        "propertyNames",
        "unevaluatedProperties",
        "unevaluatedItems",
        "minProperties",
        "maxProperties",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "$comment",
    }
)

# Character classes spelled out: the grammar converter handles [0-9] more reliably than \d.
DATE_PATTERN = r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"
TIME_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
PHONE_PATTERN = r"^[0-9]{10}$"

_DATE_HINT = re.compile(r"yyyy-mm-dd", re.IGNORECASE)
_TIME_HINT = re.compile(r"\bhh:mm\b(?!:)", re.IGNORECASE)
_PHONE_HINT = re.compile(r"\b10[- ]digit\b", re.IGNORECASE)
_ENUM_TRIGGER = re.compile(
    r"(?:either|one of|must be|can be|valid values?(?: are|:)|allowed values?(?: are|:)?"
    r"|options?(?: are|:))\s*:?\s*((?:['\"][^'\"]{1,40}['\"]\s*(?:,|/|\bor\b|\band\b)?\s*)+)",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"['\"]([^'\"]{1,40})['\"]")
_EXAMPLE_MARKERS = ("e.g.", "for example", "such as", "example")


@dataclass(frozen=True, slots=True)
class TightenOptions:
    """Switches for the grammar ablations (see docs/PLAN.md, Phase 1 week 3)."""

    # "strict" forces ISO dates in the grammar; "loose" leaves them free for the canonicalizer.
    date_grammar: Literal["strict", "loose"] = "strict"
    infer_enums: bool = True
    # Caps runaway strings; 0 disables.
    max_length: int = 512


def enum_from_description(description: str) -> list[str] | None:
    """Quoted values the description lists as the only choices, or None if it is not clear."""
    lowered = description.lower()
    if any(marker in lowered for marker in _EXAMPLE_MARKERS):
        return None
    match = _ENUM_TRIGGER.search(description)
    if match is None:
        return None
    values = list(dict.fromkeys(_QUOTED.findall(match.group(1))))
    return values if len(values) >= 2 else None


def tighten(schema: dict[str, Any], options: TightenOptions | None = None) -> dict[str, Any]:
    """Return a copy of ``schema`` with patterns, enums and length limits added.

    Dates get an ISO pattern; numbers stay numbers. Never replaces a constraint the schema
    already has, and never touches ``type`` or ``required``.
    """
    out: dict[str, Any] = _walk(copy.deepcopy(schema), options or TightenOptions())
    return out


def _walk(node: Any, options: TightenOptions) -> Any:
    if isinstance(node, list):
        return [_walk(item, options) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in UNSUPPORTED:
            continue
        if key in ("properties", "$defs", "definitions", "patternProperties") and isinstance(
            value, dict
        ):
            out[key] = {name: _walk(sub, options) for name, sub in value.items()}
        elif key in ("items", "additionalProperties", "prefixItems", "anyOf", "oneOf", "allOf"):
            out[key] = _walk(value, options)
        else:
            out[key] = value
    if out.get("type") == "string":
        _tighten_string(out, options)
    return out


def _tighten_string(node: dict[str, Any], options: TightenOptions) -> None:
    if "enum" in node or "const" in node or "pattern" in node:
        return
    description = str(node.get("description", ""))
    if options.infer_enums and "format" not in node:
        values = enum_from_description(description)
        if values:
            node["enum"] = values
            return
    if "format" not in node:
        pattern = _pattern_for(description, options)
        if pattern:
            node["pattern"] = pattern
            return
    if options.max_length and "maxLength" not in node and "format" not in node:
        node["maxLength"] = options.max_length


def _pattern_for(description: str, options: TightenOptions) -> str | None:
    if options.date_grammar == "strict" and _DATE_HINT.search(description):
        if "hh" in description.lower():
            return None  # a date-time, not a plain date
        return DATE_PATTERN
    if _TIME_HINT.search(description) and not _DATE_HINT.search(description):
        return TIME_PATTERN
    if _PHONE_HINT.search(description):
        return PHONE_PATTERN
    return None
