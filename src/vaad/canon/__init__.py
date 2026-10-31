"""Schema-aware argument canonicalizer: converts or flags, never invents.

Two uses of one parser core:
- ``annotate_turn`` writes the parsed value after each spoken-form span in the user's turn, so the
  model copies a value instead of computing one ("dedh kilo [=1.5 kg]");
- ``check_argument`` compares a value the model put in a tool call with what the turn says, and
  agrees, repairs it, or leaves it for the decision layer to flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from vaad.canon.dates import find_dates
from vaad.canon.money import find_amounts
from vaad.canon.numbers import find_numbers
from vaad.canon.phones import parse_phone
from vaad.canon.times import find_times
from vaad.canon.units import convert, find_quantities
from vaad.types import Canonicalized

_DIGITS_ONLY = re.compile(r"^[\s0-9०-९,.:/\-]+$")  # noqa: RUF001
_KIND_HINTS = (
    ("phone", ("phone", "mobile", "10-digit", "10 digit", "msisdn")),
    ("time", ("hh:mm", "24-hour", "time of")),
    ("date", ("yyyy-mm-dd", "date")),
    ("money", ("amount", "price", "rupee", "inr", "cost", "fee", "money", "salary", "emi")),
    ("quantity", ("weight", "_kg", "kilo", "gram", "litre", "liter", "quantity", "volume")),
)
_TARGET_UNIT = (("_kg", "kg"), ("kilogram", "kg"), ("_g", "g"), ("litre", "l"), ("liter", "l"),
                ("_ml", "ml"), ("_km", "km"), ("_cm", "cm"), ("_m", "m"))  # fmt: skip


@dataclass(frozen=True, slots=True)
class ArgCheck:
    """The outcome for one argument: agree, repair (``value`` replaces the model's), or leave."""

    status: str  # "agree" | "repair" | "ungrounded" | "ambiguous"
    value: Any
    confidence: float
    reason: str


def field_kind(name: str, schema: dict[str, Any]) -> str:
    """Which parser a field needs, from its name, type and description; "other" = leave alone."""
    if schema.get("type") not in ("string", "number", "integer"):
        return "other"
    text = f"{name} {schema.get('description', '')} {schema.get('format', '')}".lower()
    for kind, hints in _KIND_HINTS:
        if any(h in text for h in hints):
            numeric_kind = kind in ("money", "quantity")
            if numeric_kind != (schema.get("type") in ("number", "integer")):
                continue
            return kind
    return "other"


def _target_unit(name: str, schema: dict[str, Any]) -> str | None:
    text = f"{name} {schema.get('description', '')}".lower()
    return next((unit for hint, unit in _TARGET_UNIT if hint in text), None)


def _candidates(
    kind: str, name: str, schema: dict[str, Any], turn: str, ref_date: date
) -> list[Canonicalized]:
    field_text = f"{name} {schema.get('description', '')}"
    if kind == "money":
        return find_amounts(turn, require_marker=True)
    if kind == "quantity":
        target = _target_unit(name, schema)
        out = []
        for q in find_quantities(turn):
            value = convert(float(q.value), q.unit, target) if target else float(q.value)
            if value is not None:
                out.append(Canonicalized(value, q.confidence, q.canonicalized().source, q.unit))
        return out
    if kind == "date":
        return [m.canonicalized() for m in find_dates(turn, ref_date, field_text)]
    if kind == "time":
        return [m.canonicalized() for m in find_times(turn)]
    if kind == "phone":
        phone = parse_phone(turn)
        return [phone] if phone else []
    return []


def _same(kind: str, raw: Any, candidate: Any) -> bool:
    if kind in ("money", "quantity"):
        try:
            return abs(float(raw) - float(candidate)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(raw).strip() == str(candidate).strip()


def check_argument(
    name: str, schema: dict[str, Any], raw: Any, turn: str, ref_date: date
) -> ArgCheck | None:
    """Compare the model's ``raw`` value with the turn; None for fields we do not check."""
    kind = field_kind(name, schema)
    if kind == "other":
        return None
    found = _candidates(kind, name, schema, turn, ref_date)
    if not found:
        return ArgCheck("ungrounded", raw, 0.55, f"nothing in the turn supports this {kind}")
    for c in found:
        if _same(kind, raw, c.value):
            if c.confidence < 0.6:  # agreeing with a coin flip is not support
                return ArgCheck("ambiguous", raw, c.confidence, c.reason)
            return ArgCheck("agree", raw, c.confidence, c.reason)
    best = max(found, key=lambda c: c.confidence)
    if len(found) > 1 and sum(c.confidence >= 0.9 for c in found) > 1:
        return ArgCheck("ambiguous", raw, 0.5, f"the turn has several {kind} values")
    if best.confidence < 0.6:
        return ArgCheck("ambiguous", best.value, best.confidence, best.reason)
    return ArgCheck("repair", best.value, best.confidence, f"turn says {best.value}; {best.reason}")


def annotate_turn(turn: str, ref_date: date) -> str:
    """Append ``[=value]`` after each spoken-form number, time or date the parsers are sure of."""
    inserts: list[tuple[int, str]] = []
    covered: list[tuple[int, int]] = []  # times and dates own their numbers ("saade nau baje")
    for t in find_times(turn):
        if t.confidence >= 0.9 and not _DIGITS_ONLY.match(turn[t.start : t.end]):
            inserts.append((t.end, f" [={t.value}]"))
        covered.append((t.start, t.end))
    for d in find_dates(turn, ref_date):
        if d.confidence >= 0.9 and not _DIGITS_ONLY.match(turn[d.start : d.end]):
            inserts.append((d.end, f" [={d.value}]"))
        covered.append((d.start, d.end))
    for m in find_numbers(turn):
        span = turn[m.start : m.end]
        inside = any(a <= m.start < b for a, b in covered)
        if inside or _DIGITS_ONLY.match(span) or m.confidence < 0.9:
            continue
        inserts.append((m.end, f" [={m.value}]"))
    out, last = [], 0
    for end, note in sorted(set(inserts)):
        out.append(turn[last:end] + note)
        last = end
    out.append(turn[last:])
    return "".join(out)


__all__ = ["ArgCheck", "annotate_turn", "check_argument", "field_kind"]
