"""Shared types passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Lang(StrEnum):
    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"


class Tier(StrEnum):
    SMALL = "small"
    STRONG = "strong"


class Decision(StrEnum):
    """What the gateway does with a tool call after canonicalization."""

    PASS = "pass"
    RETRY = "retry"
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class Span:
    """Character offsets [start, end) into the user turn a value came from."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Canonicalized:
    """Result of canonicalizing one argument value.

    ``source`` is None only when the value came from the reference date (e.g. "aaj");
    gate 6 rejects any other value without a source span.
    """

    value: Any
    confidence: float
    source: Span | None
    reason: str
    from_ref_date: bool = False


@dataclass(slots=True)
class Trace:
    """One structured record per request, written as a JSON line."""

    request_id: str
    lang: Lang | None = None
    lang_confidence: float | None = None
    tier: Tier | None = None
    raw_args: list[dict[str, Any]] = field(default_factory=list)
    canon_args: list[dict[str, Any]] = field(default_factory=list)
    decision: Decision | None = None
    stage_ms: dict[str, float] = field(default_factory=dict)
