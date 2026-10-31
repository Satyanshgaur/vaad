"""Loads the time, date and direction lexicon once."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

_PATH = Path(__file__).parent / "lexicons" / "time_date.yaml"


@dataclass(frozen=True, slots=True)
class TimeDateLexicon:
    baje: frozenset[str]
    fillers: frozenset[str]
    periods: dict[str, str]  # word -> morning | afternoon | evening | night
    minutes: frozenset[str]
    hours: frozenset[str]
    months: dict[str, int]
    weekdays: dict[str, int]  # Monday = 0
    relative_days: dict[str, int]
    fixed_days: dict[str, int]
    this_words: frozenset[str]
    next_words: frozenset[str]
    last_words: frozenset[str]
    day_words: frozenset[str]
    week_words: frozenset[str]
    after_words: frozenset[str]
    before_words: frozenset[str]
    tarikh_words: frozenset[str]
    past_cues: frozenset[str]
    future_cues: frozenset[str]
    field_future: frozenset[str]
    field_past: frozenset[str]


def _set(data: dict[str, object], key: str) -> frozenset[str]:
    return frozenset(_nfc(w) for w in data[key])  # type: ignore[attr-defined]


def _nfc(word: object) -> str:
    return unicodedata.normalize("NFC", str(word).lower())


@cache
def time_date_lexicon() -> TimeDateLexicon:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
    periods = {_nfc(w): cls for cls, words in data["periods"].items() for w in words}
    months = {_nfc(w): int(n) for n, words in data["months"].items() for w in words}
    weekdays = {_nfc(w): int(n) for n, words in data["weekdays"].items() for w in words}
    return TimeDateLexicon(
        baje=_set(data, "baje"),
        fillers=_set(data, "fillers"),
        periods=periods,
        minutes=_set(data, "minutes"),
        hours=_set(data, "hours"),
        months=months,
        weekdays=weekdays,
        relative_days={_nfc(k): int(v) for k, v in data["relative_days"].items()},
        fixed_days={_nfc(k): int(v) for k, v in data["fixed_days"].items()},
        this_words=_set(data, "this_words"),
        next_words=_set(data, "next_words"),
        last_words=_set(data, "last_words"),
        day_words=_set(data, "day_words"),
        week_words=_set(data, "week_words"),
        after_words=_set(data, "after_words"),
        before_words=_set(data, "before_words"),
        tarikh_words=_set(data, "tarikh_words"),
        past_cues=_set(data, "past_cues"),
        future_cues=_set(data, "future_cues"),
        field_future=_set(data, "field_future"),
        field_past=_set(data, "field_past"),
    )
