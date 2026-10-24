from __future__ import annotations

from typing import Any

import pytest

from harness.schema import ExpectedCall, ToolCall
from harness.score import call_matches, calls_match, values_equal


def tc(name: str, **args: Any) -> ToolCall:
    return ToolCall(name=name, arguments=args)


def ec(name: str, optional: tuple[str, ...] = (), **args: list[Any]) -> ExpectedCall:
    return ExpectedCall(name=name, arguments=args, optional=list(optional))


@pytest.mark.unit
class TestValues:
    def test_numbers(self) -> None:
        assert values_equal(2, 2.0)
        assert not values_equal(2, 2.5)

    def test_bool_is_not_int(self) -> None:
        assert not values_equal(True, 1)
        assert values_equal(False, False)

    def test_strings_case_and_space(self) -> None:
        assert values_equal(" Delhi ", "delhi")
        assert not values_equal("kal", "2026-10-25")


@pytest.mark.unit
class TestCalls:
    def test_exact(self) -> None:
        assert call_matches(
            tc("ship", date="2026-10-25", weight_kg=2),
            ec("ship", date=["2026-10-25"], weight_kg=[2]),
        )

    def test_wrong_value(self) -> None:
        assert not call_matches(tc("ship", date="kal"), ec("ship", date=["2026-10-25"]))

    def test_wrong_name(self) -> None:
        assert not call_matches(tc("track"), ec("ship"))

    def test_extra_argument(self) -> None:
        assert not call_matches(tc("ship", date="x", note="y"), ec("ship", date=["x"]))

    def test_optional_missing(self) -> None:
        assert call_matches(tc("ship", date="x"), ec("ship", ("note",), date=["x"], note=["y"]))

    def test_required_missing(self) -> None:
        assert not call_matches(tc("ship"), ec("ship", date=["x"]))

    def test_free_text_present_but_not_scored(self) -> None:
        expected = ExpectedCall(name="remind", arguments={"time": ["08:00"]}, free_text=["text"])
        assert call_matches(tc("remind", time="08:00", text="kiraya bharna"), expected)
        assert not call_matches(tc("remind", time="08:00"), expected)
        assert not call_matches(tc("remind", time="08:00", text=" "), expected)

    def test_parallel_any_order(self) -> None:
        predicted = [tc("pay", amount=500), tc("pay", amount=900)]
        expected = [ec("pay", amount=[900]), ec("pay", amount=[500])]
        assert calls_match(predicted, expected)

    def test_parallel_count_mismatch(self) -> None:
        assert not calls_match([tc("pay", amount=500)], [ec("pay", amount=[500])] * 2)

    def test_relevance(self) -> None:
        assert calls_match([], [])
        assert not calls_match([tc("pay", amount=1)], [])
