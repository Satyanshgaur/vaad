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
    r"\s*(?P<unit>rupaye|rupees?|rupiye|rupaya|rupiya|rupay|rupe|rs\.?|inr|paise|paisa|"
    r"रुपये|रुपए|रुपया|रु\.?|पैसे)(?![A-Za-zऀ-ॿ])",
    re.IGNORECASE,
)
_PAISE_TAIL = re.compile(
    r"\s*(?P<n>[\w\u0900-\u097F ]{1,24}?)\s*(?:paise|paisa|पैसे)(?![\w\u0900-\u097F])", re.IGNORECASE
)
_LAKH_L = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?[lL](?![A-Za-z])")
_BEFORE = re.compile(r"(?:₹|\brs\.?|\binr)\s*$", re.IGNORECASE)
_PAISE = frozenset({"paise", "paisa", "पैसे"})


def _marker(text: str, match: NumberMatch) -> tuple[bool, bool]:
    """(has a currency marker, is paise) for a number match."""
    after = _AFTER.match(text, match.end)
    if after:
        return True, after.group("unit").lower() in _PAISE
    return bool(_BEFORE.search(text[: match.start])), False


def find_amounts(text: str, require_marker: bool = True) -> list[Canonicalized]:
    """Every amount in ``text`` in rupees, left to right. With ``require_marker`` False a lone
    unmarked number is also returned, at lower confidence."""
    matches = find_numbers(text)
    out: list[Canonicalized] = []
    for m in matches:
        marked, paise = _marker(text, m)
        if not marked:
            continue
        after = _AFTER.match(text, m.end)
        end = after.end() if after else m.end
        value = m.value / 100 if paise else m.value
        if not paise and after:  # "10 rupaye 25 paise": rupees followed by a paise number
            tail = _PAISE_TAIL.match(text, after.end())
            if tail:
                tail_numbers = find_numbers(tail.group("n"))
                if tail_numbers and float(tail_numbers[0].value) < 100:
                    value = m.value + float(tail_numbers[0].value) / 100
                    after = tail  # the span covers the paise part too
        out.append(
            Canonicalized(value, m.confidence, Span(m.start, end), f"{m.reason}; currency marker")
        )
    if not out and not require_marker:
        # a lone number in an amount field is clear enough; with several numbers and no currency
        # word it was right only about half the time (calibration card), so it asks
        cap = 0.9 if len(matches) == 1 else 0.55
        out = [
            Canonicalized(
                m.value,
                min(m.confidence, cap),
                Span(m.start, m.end),
                f"{m.reason}; no currency marker",
            )
            for m in matches
        ]
        for lakh in _LAKH_L.finditer(text):  # "5L loan", "1.5L": L as lakh in a money field
            value = float(lakh.group(1)) * 100_000
            out = [Canonicalized(int(value) if value == int(value) else value, 0.8,
                                 Span(lakh.start(), lakh.end()), "L read as lakh")]  # fmt: skip
    return out


def parse_amount(text: str, require_marker: bool = True) -> Canonicalized | None:
    """The first amount in ``text``, in rupees (see ``find_amounts``)."""
    amounts = find_amounts(text, require_marker)
    return amounts[0] if amounts else None
