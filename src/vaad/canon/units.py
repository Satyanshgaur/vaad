"""Quantities: "dedh kilo", "आधा लीटर", "2kg", "dhai sau gram" -> (value, canonical unit).

Units are not converted silently: "dhai sau gram" is 250 g. ``convert`` does it when the tool's
field asks for a particular unit (a `weight_kg` field wants kilograms).
"""

from __future__ import annotations

from dataclasses import dataclass

from vaad.canon.numbers import find_numbers
from vaad.canon.tokens import tokenize
from vaad.types import Canonicalized, Span

_UNITS = {
    "kg": "kilo kilos kg kgs kilogram kilograms kilogramme किलो किलोग्राम केजी",
    "g": "gram grams gm gms g ग्राम",
    "l": "litre litres liter liters ltr ltrs l लीटर लिटर",
    "ml": "ml millilitre millilitres मिलीलीटर मिली",
    "piece": "piece pieces pcs pc नग पीस",
    "dozen": "dozen darjan दर्जन",
    "km": "km kilometer kilometre kilometers किलोमीटर",
    "m": "meter metre meters metres मीटर",
    "cm": "cm centimeter centimetre सेंटीमीटर",
}
UNIT_OF = {word: unit for unit, words in _UNITS.items() for word in words.split()}
_TO_BASE = {("g", "kg"): 0.001, ("kg", "g"): 1000.0, ("ml", "l"): 0.001, ("l", "ml"): 1000.0,
            ("cm", "m"): 0.01, ("m", "cm"): 100.0, ("m", "km"): 0.001, ("km", "m"): 1000.0,
            ("dozen", "piece"): 12.0}  # fmt: skip


@dataclass(frozen=True, slots=True)
class QuantityMatch:
    value: int | float
    unit: str
    start: int
    end: int
    confidence: float

    def canonicalized(self) -> Canonicalized:
        return Canonicalized(
            {"value": self.value, "unit": self.unit},
            self.confidence,
            Span(self.start, self.end),
            f"{self.value} {self.unit}",
        )


def convert(value: float, unit: str, target: str) -> float | None:
    """``value`` in ``unit`` expressed in ``target``; None if the pair is not convertible."""
    if unit == target:
        return value
    factor = _TO_BASE.get((unit, target))
    return None if factor is None else round(value * factor, 9)


def find_quantities(text: str) -> list[QuantityMatch]:
    tokens = tokenize(text)
    out: list[QuantityMatch] = []
    for m in find_numbers(text):
        after = next((t for t in tokens if t.start >= m.end), None)
        if after is None or after.norm not in UNIT_OF:
            continue
        value = m.value
        out.append(QuantityMatch(value, UNIT_OF[after.norm], m.start, after.end, m.confidence))
    return out


def parse_quantity(text: str) -> Canonicalized | None:
    found = find_quantities(text)
    return found[0].canonicalized() if found else None


__all__ = ["UNIT_OF", "QuantityMatch", "convert", "find_quantities", "parse_quantity"]
