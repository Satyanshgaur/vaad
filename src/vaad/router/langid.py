"""Deterministic language ID: script check plus a Hinglish word-list score. Phase 3."""

from __future__ import annotations

from dataclasses import dataclass

from vaad.types import Lang


@dataclass(frozen=True, slots=True)
class LangResult:
    lang: Lang
    confidence: float


def detect(text: str) -> LangResult:
    """Classify a user turn as en, hi (Devanagari) or hinglish (Romanized). Must stay < 1 ms."""
    raise NotImplementedError("Phase 3")
