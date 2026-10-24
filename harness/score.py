"""Full tool-call correctness: function name plus every argument, BFCL-style.

Each expected argument lists its acceptable values. Parallel calls match in any order.
"""

from __future__ import annotations

from itertools import permutations
from typing import Any

from harness.schema import ExpectedCall, ToolCall

MAX_PERMUTED_CALLS = 7


def values_equal(predicted: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(predicted, bool):
        return predicted is expected
    if isinstance(expected, int | float) and isinstance(predicted, int | float):
        return abs(float(predicted) - float(expected)) < 1e-9
    if isinstance(expected, str) and isinstance(predicted, str):
        return predicted.strip().casefold() == expected.strip().casefold()
    if isinstance(expected, list) and isinstance(predicted, list):
        return len(expected) == len(predicted) and all(
            values_equal(p, e) for p, e in zip(predicted, expected, strict=True)
        )
    if isinstance(expected, dict) and isinstance(predicted, dict):
        return expected.keys() == predicted.keys() and all(
            values_equal(predicted[k], expected[k]) for k in expected
        )
    return bool(predicted == expected)


def call_matches(predicted: ToolCall, expected: ExpectedCall) -> bool:
    if predicted.name != expected.name:
        return False
    if predicted.arguments.keys() - expected.arguments.keys() - set(expected.free_text):
        return False  # hallucinated argument
    for arg in expected.free_text:
        value = predicted.arguments.get(arg)
        if not (isinstance(value, str) and value.strip()):
            return False
    for arg, acceptable in expected.arguments.items():
        if arg not in predicted.arguments:
            if arg in expected.optional:
                continue
            return False
        if not any(values_equal(predicted.arguments[arg], v) for v in acceptable):
            return False
    return True


def calls_match(predicted: list[ToolCall], expected: list[ExpectedCall]) -> bool:
    """True when the predicted calls are exactly the expected ones, in any order."""
    if len(predicted) != len(expected):
        return False
    if not expected:
        return True  # irrelevance or clarify task: correctly called nothing
    if len(expected) > MAX_PERMUTED_CALLS:
        return _greedy_match(predicted, expected)
    return any(
        all(call_matches(p, e) for p, e in zip(perm, expected, strict=True))
        for perm in permutations(predicted)
    )


def _greedy_match(predicted: list[ToolCall], expected: list[ExpectedCall]) -> bool:
    remaining = list(predicted)
    for e in expected:
        hit = next((p for p in remaining if call_matches(p, e)), None)
        if hit is None:
            return False
        remaining.remove(hit)
    return True
