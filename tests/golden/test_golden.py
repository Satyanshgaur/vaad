"""Gate 4: fixed input -> expected canonical value, from tests/golden/canon_cases.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vaad.canon.money import parse_amount
from vaad.canon.numbers import find_numbers, parse_number

CASES = yaml.safe_load((Path(__file__).parent / "canon_cases.yaml").read_text("utf-8"))["cases"]


def _id(case: dict[str, object]) -> str:
    return f"{case['type']}:{case['input']}"


@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=_id)
def test_golden(case: dict[str, object]) -> None:
    text = str(case["input"])
    if case["type"] == "money":
        got = parse_amount(text, require_marker=not case.get("field_is_amount", False))
        if case["expected"] in (None, "none"):
            assert got is None, f"{text!r} is not money, got {got}"
        else:
            assert got is not None, f"{text!r} found no amount"
            assert got.value == pytest.approx(case["expected"])
        return
    assert case["type"] == "number", f"no golden runner for type {case['type']}"
    if "all" in case:
        assert [m.value for m in find_numbers(text)] == case["all"]
        return
    got = parse_number(text)
    if case["expected"] is None or case["expected"] == "none":
        assert got is None, f"{text!r} should have no number, got {got}"
    else:
        assert got is not None, f"{text!r} found no number"
        assert got.value == pytest.approx(case["expected"])
