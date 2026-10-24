"""Schema-aware argument canonicalizer: converts or flags, never invents. Phase 2 (weeks 4-5)."""

from __future__ import annotations

from datetime import date
from typing import Any

from vaad.types import Canonicalized


def canonicalize(
    field_schema: dict[str, Any], raw: Any, turn: str, ref_date: date
) -> Canonicalized:
    """Canonicalize one argument value against its JSON-schema field.

    The schema decides the value type (number, money, date, time, phone, unit) and whether the
    field is free text, which is passed through untouched.
    """
    raise NotImplementedError("Phase 2")


__all__ = ["canonicalize"]
