"""Gate 5 (round trips, idempotence, free text untouched) and gate 6 (no value invention)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vaad.canon.lexicon import number_lexicon
from vaad.canon.numbers import find_numbers, parse_number

LEX = number_lexicon()
# one spelling per value, Romanized and Devanagari
ROMAN = {v: k for k, v in reversed(list(LEX.units.items())) if k.isascii()}
DEVA = {v: k for k, v in reversed(list(LEX.units.items())) if not k.isascii()}
MULT = {"roman": {100: "sau", 1000: "hazaar", 100_000: "lakh", 10_000_000: "crore"},
        "deva": {100: "सौ", 1000: "हज़ार", 100_000: "लाख", 10_000_000: "करोड़"}}  # fmt: skip


def spell(n: int, script: str) -> str:
    """The Hindi reading of 1 <= n < 10**9, crore/lakh/hazaar/sau groups then the last 0-99."""
    units = ROMAN if script == "roman" else DEVA
    mult = MULT[script]
    parts: list[str] = []
    for size in (10_000_000, 100_000, 1000):
        count, n = divmod(n, size)
        if count:
            parts += [units[count], mult[size]]
    hundreds, rest = divmod(n, 100)
    if hundreds:
        parts += [units[hundreds], mult[100]]
    if rest:
        parts.append(units[rest])
    return " ".join(parts)


@pytest.mark.property
@settings(max_examples=400, deadline=None)
@given(st.integers(min_value=1, max_value=999_999_999), st.sampled_from(["roman", "deva"]))
def test_spoken_number_round_trips(n: int, script: str) -> None:
    # a currency word after it removes the "do"/"saath" ambiguity, as in real requests
    suffix = " rupaye" if script == "roman" else " रुपये"
    got = parse_number(spell(n, script) + suffix)
    assert got is not None
    assert got.value == n


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(st.integers(min_value=0, max_value=10**9), st.sampled_from(["", ","]))
def test_digits_round_trip(n: int, sep: str) -> None:
    text = f"{n:,}" if sep else str(n)
    got = parse_number(f"amount {text} rupaye")
    assert got is not None and got.value == n


WORDS = ["mera", "order", "bhej", "kal", "tak", "wala", "hai", "ka", "kar", "mausam", "batao",
         "delivery", "payment", "aaj", "shaam", "ko", "mein", "aur", "भेज", "कल", "तक", "मौसम",
         "ऑर्डर", "बताओ", "का", "है"]  # fmt: skip
NUMBERS = [
    "5",
    "2.5",
    "1,50,000",
    "nau sau",
    "dedh lakh",
    "paanch hazaar",
    "saade teen sau",
    "डेढ़ सौ",
]


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(st.lists(st.sampled_from(WORDS), min_size=0, max_size=12))
def test_text_without_numbers_is_untouched(words: list[str]) -> None:
    assert find_numbers(" ".join(words)) == []


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(st.lists(st.sampled_from(WORDS + NUMBERS), min_size=0, max_size=14))
def test_every_value_traces_to_a_span(tokens: list[str]) -> None:
    """Gate 6: spans are inside the text, ordered, non-overlapping, and re-parse to the value."""
    text = " ".join(tokens)
    matches = find_numbers(text)
    previous_end = 0
    for m in matches:
        assert 0 <= m.start < m.end <= len(text)
        assert m.start >= previous_end
        previous_end = m.end
        again = parse_number(text[m.start : m.end])
        assert again is not None and again.value == m.value  # idempotent on its own span
        assert 0.0 < m.confidence <= 1.0
    # nothing is invented: no number can appear when the text has no digit and no number word
    if not any(t in NUMBERS for t in tokens):
        assert matches == []
