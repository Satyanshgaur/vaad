"""Gate 4: fixed input -> expected canonical value, from tests/golden/canon_cases.yaml."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from vaad.canon.dates import parse_date
from vaad.canon.money import parse_amount
from vaad.canon.numbers import find_numbers, parse_number
from vaad.canon.phones import parse_phone
from vaad.canon.times import parse_duration, parse_time
from vaad.canon.units import parse_quantity

CASES = [
    case
    for name in ("canon_cases.yaml", "canon_cases_ai.yaml")
    for case in yaml.safe_load((Path(__file__).parent / name).read_text("utf-8"))["cases"]
]


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
    if case["type"] in ("phone", "quantity"):
        got = parse_phone(text) if case["type"] == "phone" else parse_quantity(text)
        if case["expected"] in (None, "none"):
            assert got is None, f"{text!r} should have no {case['type']}, got {got}"
        elif case["expected"] == "ambiguous":
            assert got is not None and got.confidence < 0.6, f"{text!r}: {got}"
        else:
            assert got is not None, f"{text!r} found no {case['type']}"
            if case["type"] == "phone":
                assert got.value == case["expected"], f"{text!r}: {got}"
            else:
                assert got.value["unit"] == case["expected"]["unit"], f"{text!r}: {got}"
                assert got.value["value"] == pytest.approx(case["expected"]["value"]), (
                    f"{text!r}: {got}"
                )
        return
    if case["type"] in ("time", "duration", "date"):
        if case["type"] == "time":
            got = parse_time(text)
        elif case["type"] == "duration":
            got = parse_duration(text)
        else:
            got = parse_date(text, date.fromisoformat(case["ref"]), case.get("field"))  # type: ignore[arg-type]
        if case["expected"] in (None, "none"):
            assert got is None, f"{text!r} should have no {case['type']}, got {got}"
        elif case["expected"] == "ambiguous":
            assert got is not None and got.confidence < 0.6, f"{text!r}: {got}"
        else:
            assert got is not None, f"{text!r} found no {case['type']}"
            assert got.value == case["expected"], f"{text!r}: {got}"
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
