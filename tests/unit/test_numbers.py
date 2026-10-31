from __future__ import annotations

import pytest

from vaad.canon.lexicon import number_lexicon
from vaad.canon.numbers import find_numbers, parse_number
from vaad.types import Canonicalized


@pytest.mark.unit
def test_lexicon_covers_zero_to_ninety_nine_in_both_scripts() -> None:
    lex = number_lexicon()
    roman = {v for k, v in lex.units.items() if k.isascii()}
    deva = {v for k, v in lex.units.items() if not k.isascii()}
    assert roman == set(range(100))
    assert deva == set(range(100))


@pytest.mark.unit
def test_parse_number_returns_a_canonicalized_with_a_span() -> None:
    text = "mujhe dedh lakh ka loan chahiye"
    got = parse_number(text)
    assert isinstance(got, Canonicalized)
    assert got.value == 150000
    assert got.source is not None
    assert text[got.source.start : got.source.end] == "dedh lakh"
    assert got.confidence > 0.9 and got.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "low"),
    [("do order", True), ("saath hazaar", True), ("ek order", True), ("do kilo", False)],
)
def test_ambiguous_words_get_lower_confidence_than_clear_numbers(text: str, low: bool) -> None:
    got = parse_number(text)
    assert got is not None
    assert (got.confidence < 0.9) is low


@pytest.mark.unit
def test_adjacent_small_numbers_are_not_summed() -> None:
    assert [m.value for m in find_numbers("do teen din")] == [2, 3]
    assert [m.value for m in find_numbers("5 6")] == [5, 6]


@pytest.mark.unit
def test_groups_must_decrease() -> None:
    # "hazaar" before "lakh" is not one number
    assert [m.value for m in find_numbers("do hazaar ek lakh")] == [2000, 100000]


@pytest.mark.unit
def test_identifiers_with_digits_are_not_quantities() -> None:
    assert find_numbers("order OD4821") == []
    assert [m.value for m in find_numbers("order OD4821, 2kg")] == [2]
