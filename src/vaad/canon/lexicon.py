"""Loads the number lexicons (Romanized Hinglish and Devanagari) once."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

import yaml

_DIR = Path(__file__).parent / "lexicons"


@dataclass(frozen=True, slots=True)
class NumberLexicon:
    units: dict[str, int]
    multipliers: dict[str, int]
    fractions: dict[str, Fraction]
    modifiers: dict[str, Fraction]
    verb_stems: frozenset[str]
    number_followers: frozenset[str]
    ambiguous: frozenset[str]


def _fractions(raw: dict[str, float]) -> dict[str, Fraction]:
    return {word: Fraction(str(value)) for word, value in raw.items()}


@cache
def number_lexicon() -> NumberLexicon:
    """Both scripts merged: Romanized keys are lower-case, Devanagari keys are as written."""
    merged: dict[str, dict[str, object]] = {}
    lists: dict[str, set[str]] = {
        "verb_stems": set(),
        "number_followers": set(),
        "ambiguous_units": set(),
    }
    for name in ("hinglish_numbers.yaml", "hindi_numbers.yaml"):
        data = yaml.safe_load((_DIR / name).read_text(encoding="utf-8"))
        for section in ("units", "multipliers", "fractions", "modifiers"):
            merged.setdefault(section, {}).update(data.get(section, {}))
        for section, bucket in lists.items():
            bucket.update(data.get(section, []))
    return NumberLexicon(
        units={k: int(v) for k, v in merged["units"].items()},  # type: ignore[call-overload]
        multipliers={k: int(v) for k, v in merged["multipliers"].items()},  # type: ignore[call-overload]
        fractions=_fractions(merged["fractions"]),  # type: ignore[arg-type]
        modifiers=_fractions(merged["modifiers"]),  # type: ignore[arg-type]
        verb_stems=frozenset(lists["verb_stems"]),
        number_followers=frozenset(lists["number_followers"]),
        ambiguous=frozenset(lists["ambiguous_units"]),
    )
