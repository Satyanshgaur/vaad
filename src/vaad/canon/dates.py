"""Relative dates (aaj, kal, parson, agle somvaar) resolved against a reference date.

"kal" is both yesterday and tomorrow: resolve from verb tense and the field's semantics,
otherwise flag instead of guessing."""

from __future__ import annotations

from datetime import date

from vaad.types import Canonicalized


def parse_date(text: str, ref_date: date, field_name: str = "") -> Canonicalized | None:
    raise NotImplementedError("Phase 2")
