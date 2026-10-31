"""Loads the number lexicons (Romanized Hinglish and Devanagari) once."""

from __future__ import annotations

import unicodedata
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
    return {_key(word): Fraction(str(value)) for word, value in raw.items()}


def _key(word: str) -> str:
    return unicodedata.normalize("NFC", str(word).lower())


def _spellings(table: dict[str, int]) -> dict[str, int]:
    """Add the v/w variants of Romanized words (bavan/bawan, tirasi/tiraasi are separate lines)."""
    out = dict(table)
    for word, value in table.items():
        if word.isascii():
            for a, b in (("v", "w"), ("w", "v")):
                if a in word:
                    out.setdefault(word.replace(a, b), value)
    return out


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
        units=_spellings({_key(k): int(v) for k, v in merged["units"].items()}),  # type: ignore[call-overload]
        multipliers=_spellings({_key(k): int(v) for k, v in merged["multipliers"].items()}),  # type: ignore[call-overload]
        fractions=_fractions(merged["fractions"]),  # type: ignore[arg-type]
        modifiers=_fractions(merged["modifiers"]),  # type: ignore[arg-type]
        verb_stems=frozenset(_key(w) for w in lists["verb_stems"]),
        number_followers=frozenset(_key(w) for w in lists["number_followers"]),
        ambiguous=frozenset(_key(w) for w in lists["ambiguous_units"]),
    )
