"""Indian money: "5 lakh", "ढाई करोड़", "Rs 500", "500 rupaye" -> amounts in rupees.

An amount is a number next to a currency marker (rupaye, rupees, Rs, INR, a rupee sign...). A
number with no marker is not money unless the caller says the field is an amount, and then its
confidence is lower. "paise" are divided by 100.
"""

from __future__ import annotations

import re

from vaad.canon.numbers import NumberMatch, find_numbers
from vaad.types import Canonicalized, Span

_AFTER = re.compile(
    r"\s*(?P<unit>rupaye|rupees?|rupiye|rupaya|rupiya|rs\.?|inr|paise|paisa|"
    r"रुपये|रुपए|रुपया|रु\.?|पैसे)(?![A-Za-zऀ-ॿ])",
    re.IGNORECASE,
)
_BEFORE = re.compile(r"(?:₹|\brs\.?|\binr)\s*$", re.IGNORECASE)
_PAISE = frozenset({"paise", "paisa", "पैसे"})


def _marker(text: str, match: NumberMatch) -> tuple[bool, bool]:
    """(has a currency marker, is paise) for a number match."""
    after = _AFTER.match(text, match.end)
    if after:
        return True, after.group("unit").lower() in _PAISE
    return bool(_BEFORE.search(text[: match.start])), False


def parse_amount(text: str, require_marker: bool = True) -> Canonicalized | None:
    """The first amount in ``text``, in rupees. With ``require_marker`` False (the schema says the
    field is an amount) the first number is returned with lower confidence."""
    matches = find_numbers(text)
    for m in matches:
        marked, paise = _marker(text, m)
        if marked:
            value = m.value / 100 if paise else m.value
            end = m.end
            after = _AFTER.match(text, m.end)
            if after:
                end = after.end()
            return Canonicalized(
                value, m.confidence, Span(m.start, end), f"{m.reason}; currency marker"
            )
    if not require_marker and matches:
        m = matches[0]
        return Canonicalized(
            m.value, min(m.confidence, 0.8), Span(m.start, m.end), f"{m.reason}; no currency marker"
        )
    return None
