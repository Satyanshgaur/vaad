"""Dates: "kal", "parson", "agle somvaar", "12 March", "पंद्रह तारीख", "teen din baad".

Everything is resolved against a reference date. "kal" is tomorrow or yesterday and "parson" the
day after tomorrow or the day before yesterday; the direction comes from the tense of the clause
and from what the field means (a delivery date is in the future, a statement's end date in the
past). With no cue the result has low confidence and lists both readings, so the decision layer
can ask instead of guessing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from vaad.canon.lexicon import number_lexicon
from vaad.canon.lexicon_time import TimeDateLexicon, time_date_lexicon
from vaad.canon.numbers import find_numbers
from vaad.canon.tokens import Token, tokenize
from vaad.types import Canonicalized, Span

_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_NUMERIC = re.compile(r"(?<![\d/.-])(\d{1,2})[/-](\d{1,2})[/-](\d{4}|\d{2})(?![\d/-])")
_SENTENCE_END = frozenset(".?!|।\n")
_FIELD_WORDS = re.compile(r"[A-Za-z]+")
_IMPERATIVE_VERBS = frozenset(
    {"do", "दो", "dena", "dijiye", "dijiyega", "दीजिए", "दीजिये", "देना", "dein", "दें"}
)
_VERB_STEMS = number_lexicon().verb_stems


@dataclass(frozen=True, slots=True)
class DateMatch:
    value: str  # ISO "YYYY-MM-DD", the most likely reading
    start: int
    end: int
    confidence: float
    reason: str
    alternatives: tuple[str, ...] = ()

    def canonicalized(self) -> Canonicalized:
        reason = self.reason
        if self.alternatives:
            reason += f"; also possible: {', '.join(self.alternatives)}"
        return Canonicalized(self.value, self.confidence, Span(self.start, self.end), reason)


# --- direction: is the date in the future (+1) or the past (-1)? -------------------------
def _field_sign(field: str | None, lex: TimeDateLexicon) -> int:
    if not field:
        return 0
    words = {w.lower() for w in _FIELD_WORDS.findall(field.replace("_", " "))}
    future, past = len(words & lex.field_future), len(words & lex.field_past)
    return (future > past) - (future < past)


def _clause_bounds(tokens: list[Token], index: int) -> tuple[int, int]:
    low, high = index, index
    while low > 0 and not (tokens[low - 1].kind == "sym" and tokens[low - 1].text in _SENTENCE_END):
        low -= 1
    while high + 1 < len(tokens) and not (
        tokens[high + 1].kind == "sym" and tokens[high + 1].text in _SENTENCE_END
    ):
        high += 1
    return low, high


def _direction(
    tokens: list[Token], first: int, last: int, field: str | None, lex: TimeDateLexicon
) -> tuple[int, float, str]:
    """(+1 future, -1 past, 0 unknown), confidence, why."""
    low, high = _clause_bounds(tokens, first)
    window = [(i, t) for i, t in enumerate(tokens[low : high + 1], low) if not first <= i <= last]
    words = [t.norm for _, t in window]
    past, future = sum(w in lex.past_cues for w in words), sum(w in lex.future_cues for w in words)
    # "bhej do", "kar do", "de dijiye": a verb stem plus a giving verb is an imperative
    for i, t in window:
        if t.norm in _IMPERATIVE_VERBS and i > 0 and tokens[i - 1].norm in _VERB_STEMS:
            future += 1
    text_sign = (future > past) - (future < past)
    field_sign = _field_sign(field, lex)
    if text_sign:
        both = past and future
        conf = 0.75 if both else 0.9
        why = f"{'future' if text_sign > 0 else 'past'} tense cue"
        if field_sign and field_sign != text_sign:
            return text_sign, conf - 0.25, why + " (field suggests the opposite)"
        return text_sign, conf, why
    if field_sign:
        return field_sign, 0.8, f"field suggests {'future' if field_sign > 0 else 'past'}"
    return 0, 0.5, "no tense cue and no field cue"


def _directional(
    base: date, offset: int, tokens: list[Token], first: int, last: int, field: str | None,
    lex: TimeDateLexicon, label: str,
) -> tuple[str, float, str, tuple[str, ...]]:  # fmt: skip
    sign, conf, why = _direction(tokens, first, last, field, lex)
    future, past = base + timedelta(days=offset), base - timedelta(days=offset)
    if sign > 0:
        return future.isoformat(), conf, f"{label} as future: {why}", ()
    if sign < 0:
        return past.isoformat(), conf, f"{label} as past: {why}", ()
    # unknown: the future reading is the likelier prior, but the result is flagged by its confidence
    return future.isoformat(), conf, f"{label}: {why}", (past.isoformat(),)


# --- helpers -------------------------------------------------------------------------------
def _index_at(tokens: list[Token], offset: int, *, end: bool = False) -> int:
    for i, token in enumerate(tokens):
        if (token.end >= offset) if end else (token.start >= offset):
            return i
    return len(tokens)


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_weekday(ref: date, weekday: int, sign: int, strict: bool) -> date:
    delta = (weekday - ref.weekday()) % 7
    if sign >= 0:
        return ref + timedelta(days=delta or (7 if strict else 0))
    back = (ref.weekday() - weekday) % 7
    return ref - timedelta(days=back or 7)


def _year_for(day: int, month: int, ref: date, sign: int) -> date | None:
    """A date with no year: this year, or next (past: last) if that points the wrong way."""
    this = _valid(ref.year, month, day)
    if this is None:
        return None
    if sign > 0 and this < ref:
        return _valid(ref.year + 1, month, day)
    if sign < 0 and this > ref:
        return _valid(ref.year - 1, month, day)
    return this


def _number_before(
    text: str, tokens: list[Token], index: int, lex: TimeDateLexicon
) -> tuple[int, int, int] | None:
    """A day number ending right before token ``index`` (one filler word allowed)."""
    boundary = tokens[index].start
    cutoff = (
        tokens[index - 1].start if index > 0 and tokens[index - 1].norm in lex.fillers else boundary
    )
    for m in find_numbers(text[:boundary]):
        if m.end <= cutoff and 1 <= float(m.value) <= 31 and float(m.value) == int(m.value):
            gap = text[m.end : boundary].strip().lower()
            if gap in ("", "ko", "ka", "को", "का", "th", "st", "nd", "rd", "tarikh", "तारीख"):
                return int(m.value), m.start, m.end
    return None


def _find_year(tokens: list[Token], after: int) -> tuple[int, int] | None:
    if (
        after < len(tokens)
        and tokens[after].kind == "digits"
        and re.fullmatch(r"\d{4}", tokens[after].text)
    ):
        return int(tokens[after].text), after
    return None


# --- finders -------------------------------------------------------------------------------
def _explicit(text: str, ref: date) -> list[DateMatch]:
    out: list[DateMatch] = []
    for m in _ISO.finditer(text):
        d = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            out.append(DateMatch(d.isoformat(), m.start(), m.end(), 1.0, "ISO date"))
    for m in _NUMERIC.finditer(text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = y + 2000 if y < 100 else y
        dmy, mdy = _valid(year, b, a), _valid(year, a, b)
        if dmy and mdy and dmy != mdy:
            out.append(
                DateMatch(
                    dmy.isoformat(),
                    m.start(),
                    m.end(),
                    0.7,
                    "DD/MM/YYYY (day first)",
                    (mdy.isoformat(),),
                )
            )
        elif dmy or mdy:
            d = dmy or mdy
            assert d is not None
            out.append(DateMatch(d.isoformat(), m.start(), m.end(), 0.9, "numeric date"))
    return out


def _month_dates(
    text: str, tokens: list[Token], ref: date, field: str | None, lex: TimeDateLexicon
) -> list[DateMatch]:
    out: list[DateMatch] = []
    for i, token in enumerate(tokens):
        month = lex.months.get(token.norm)
        if month is None or token.kind != "word":
            continue
        day: tuple[int, int, int] | None = _number_before(text, tokens, i, lex)
        end_index = i
        if day is None and i + 1 < len(tokens) and tokens[i + 1].kind == "digits":
            raw = tokens[i + 1].text
            if raw.isdigit() and 1 <= int(raw) <= 31:
                day, end_index = (int(raw), tokens[i + 1].start, tokens[i + 1].end), i + 1
        if day is None:
            continue
        sign, _, _ = _direction(tokens, i, end_index, field, lex)
        assumed = sign == 0
        sign = sign or 1
        year = _find_year(tokens, end_index + 1)
        if year:
            d = _valid(year[0], month, day[0])
            end = tokens[year[1]].end
            why = "day, month and year"
            conf = 0.95
        else:
            d = _year_for(day[0], month, ref, sign)
            end = tokens[end_index].end
            why = "day and month (year assumed)"
            conf = 0.75 if assumed else 0.85
        if d:
            out.append(DateMatch(d.isoformat(), min(day[1], token.start), end, conf, why))
    return out


def find_dates(text: str, ref_date: date, field: str | None = None) -> list[DateMatch]:
    """Every date expression in ``text``, left to right, resolved against ``ref_date``."""
    lex = time_date_lexicon()
    tokens = tokenize(text)
    explicit_sign = _field_sign(field, lex)
    out = _explicit(text, ref_date) + _month_dates(text, tokens, ref_date, field, lex)
    taken = [(m.start, m.end) for m in out]

    def free(start: int, end: int) -> bool:
        return not any(start < e and s < end for s, e in taken)

    for i, token in enumerate(tokens):
        if token.kind != "word" or not free(token.start, token.end):
            continue
        word = token.norm
        if word in lex.relative_days:
            offset = lex.relative_days[word]
            if offset == 0:
                out.append(DateMatch(ref_date.isoformat(), token.start, token.end, 1.0, "today"))
                continue
            value, conf, why, alts = _directional(ref_date, offset, tokens, i, i, field, lex, word)
            out.append(DateMatch(value, token.start, token.end, conf, why, alts))
        elif word in lex.weekdays:
            wd = lex.weekdays[word]
            prev = tokens[i - 1].norm if i > 0 else ""
            start = token.start
            if prev in lex.next_words:
                out.append(
                    DateMatch(
                        _next_weekday(ref_date, wd, 1, True).isoformat(),
                        tokens[i - 1].start,
                        token.end,
                        0.9,
                        "next weekday",
                    )
                )
                continue
            if prev in lex.last_words:
                out.append(
                    DateMatch(
                        _next_weekday(ref_date, wd, -1, True).isoformat(),
                        tokens[i - 1].start,
                        token.end,
                        0.9,
                        "last weekday",
                    )
                )
                continue
            sign, conf, why = _direction(tokens, i, i, field, lex)
            sign = sign or 1
            same = ref_date.weekday() == wd
            d = _next_weekday(ref_date, wd, sign, True)
            alts = (ref_date.isoformat(),) if same else ()
            out.append(
                DateMatch(
                    d.isoformat(),
                    start,
                    token.end,
                    0.65 if conf == 0.5 else min(conf, 0.85 if not same else 0.6),
                    f"weekday: {why}",
                    alts,
                )
            )
    out += _offset_dates(text, tokens, ref_date, lex, free)
    out += _tarikh(text, tokens, ref_date, explicit_sign, lex, free)
    # overlapping readings of the same words ("March 12 March"): keep the stronger one
    out.sort(key=lambda m: (m.start, -m.confidence, -(m.end - m.start)))
    kept: list[DateMatch] = []
    for m in out:
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    return kept


def _offset_dates(
    text: str,
    tokens: list[Token],
    ref: date,
    lex: TimeDateLexicon,
    free: Callable[[int, int], bool],
) -> list[DateMatch]:
    """ "teen din baad" (in 3 days), "do hafte pehle" (2 weeks ago)."""
    out: list[DateMatch] = []
    for m in find_numbers(text):
        nxt = _index_at(tokens, m.end)
        if nxt + 1 >= len(tokens):
            continue
        unit, direction = tokens[nxt].norm, tokens[nxt + 1].norm
        days = 1 if unit in lex.day_words else 7 if unit in lex.week_words else 0
        if not days or float(m.value) != int(m.value):
            continue
        if direction in lex.after_words and unit in lex.day_words | lex.week_words:
            sign = 1
        elif direction in lex.before_words:
            sign = -1
        else:
            continue
        end = tokens[nxt + 1].end
        if not free(m.start, end):
            continue
        d = ref + timedelta(days=sign * days * int(m.value))
        out.append(
            DateMatch(d.isoformat(), m.start, end, 0.9, f"{int(m.value)} {unit} {direction}")
        )
    return out


def _tarikh(
    text: str,
    tokens: list[Token],
    ref: date,
    sign: int,
    lex: TimeDateLexicon,
    free: Callable[[int, int], bool],
) -> list[DateMatch]:
    """ "15 tarikh": that day of this month, or the next month if it already passed."""
    out: list[DateMatch] = []
    for i, token in enumerate(tokens):
        if token.norm not in lex.tarikh_words or token.kind != "word":
            continue
        found = _number_before(text, tokens, i, lex)
        if not found or not free(found[1], token.end):
            continue
        day = found[0]
        d = _valid(ref.year, ref.month, day)
        if d is None:
            continue
        if sign >= 0 and d < ref:
            nxt_month = ref.month % 12 + 1
            d = _valid(ref.year + (ref.month == 12), nxt_month, day) or d
        out.append(
            DateMatch(d.isoformat(), found[1], token.end, 0.7, "day of month (month assumed)")
        )
    return out


def parse_date(text: str, ref_date: date, field: str | None = None) -> Canonicalized | None:
    """The first date in ``text`` as "YYYY-MM-DD"; None if there is none.

    ``field`` is the tool field's name and description; it fixes the direction of "kal" and
    "parson" when the sentence has no tense cue.
    """
    dates = find_dates(text, ref_date, field)
    return dates[0].canonicalized() if dates else None
