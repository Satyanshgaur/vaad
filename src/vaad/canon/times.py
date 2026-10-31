"""Clock times and durations: "saade nau baje", "शाम को पांच बजे", "9:30 pm", "आधे घंटे".

Clock times come back as 24-hour "HH:MM". A bare "paanch baje" is genuinely ambiguous (05:00 or
17:00); it is returned with low confidence and both readings, so the decision layer can ask.
A period word (subah, dopahar, shaam, raat), am/pm, or an hour of 13 or more settles it.
Durations ("pandrah minute", "dedh ghante") come back in minutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vaad.canon.lexicon_time import TimeDateLexicon, time_date_lexicon
from vaad.canon.numbers import NumberMatch, find_numbers
from vaad.canon.tokens import Token, tokenize
from vaad.types import Canonicalized, Span

_AMPM = r"(?P<ampm>a\.?\s?m\.?|p\.?\s?m\.?|ए\.?\s?एम\.?|ऐ\.?\s?एम\.?|पी\.?\s?एम\.?)"
_COLON = re.compile(
    rf"(?<![\d:.])(?P<h>\d{{1,2}}):(?P<m>\d{{2}})(?::\d{{2}})?(?!\d)\s*{_AMPM}?", re.I
)
_DOT_MARKED = re.compile(
    rf"(?<![\d:.])(?P<h>\d{{1,2}})\.(?P<m>\d{{2}})(?!\d)\s*(?:{_AMPM}|(?P<baje>baje|बजे))", re.I
)
_HOUR_AMPM = re.compile(rf"(?<![\d:.])(?P<h>\d{{1,2}})\s*{_AMPM}(?![A-Za-z])", re.I)
_AMPM_TAIL = re.compile(rf"\s*{_AMPM}(?![A-Za-z\u0900-\u097F])", re.I)
_PERIOD_RADIUS = 3


@dataclass(frozen=True, slots=True)
class TimeMatch:
    value: str  # "HH:MM", the most likely reading
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


@dataclass(frozen=True, slots=True)
class DurationMatch:
    minutes: int | float
    start: int
    end: int
    confidence: float
    reason: str

    def canonicalized(self) -> Canonicalized:
        return Canonicalized(self.minutes, self.confidence, Span(self.start, self.end), self.reason)


def _fmt(hour: int, minute: int) -> str:
    return f"{hour % 24:02d}:{minute:02d}"


def _from_ampm(hour: int, minute: int, ampm: str) -> tuple[str, float, str]:
    pm = ampm.lower().startswith(("p", "प"))
    h = hour % 12 + (12 if pm else 0)
    return _fmt(h, minute), 0.98, f"explicit {'pm' if pm else 'am'}"


def _from_period(hour: int, minute: int, period: str) -> tuple[str, float, str] | None:
    """Resolve a 1-12 hour with a spoken part of the day; None if the pair is odd."""
    if period == "morning":
        return (_fmt(hour, minute), 0.95, "morning") if 1 <= hour <= 11 else (
            _fmt(12, minute), 0.6, "morning 12")  # fmt: skip
    if period == "afternoon":
        if hour == 12:
            return _fmt(12, minute), 0.95, "afternoon"
        if 1 <= hour <= 6:
            return _fmt(hour + 12, minute), 0.95, "afternoon"
        if 10 <= hour <= 11:
            return _fmt(hour, minute), 0.8, "late-morning 'dopahar'"
        return None
    if period == "evening":
        if 3 <= hour <= 11:
            return _fmt(hour + 12, minute), 0.95, "evening"
        return (_fmt(hour + 12, minute), 0.7, "evening") if hour in (1, 2) else None
    if period == "night":
        if 6 <= hour <= 11:
            return _fmt(hour + 12, minute), 0.95, "night"
        if hour == 12:
            return _fmt(0, minute), 0.9, "midnight"
        if 1 <= hour <= 5:
            return _fmt(hour, minute), 0.9, "small hours"
    return None


def _bare(hour: int, minute: int) -> tuple[str, float, str, tuple[str, ...]]:
    """No period and no am/pm: ambiguous, so low confidence and both readings."""
    if hour >= 13 or hour == 0:
        return _fmt(hour, minute), 0.95, "24-hour", ()
    am, pm = _fmt(hour, minute), _fmt(hour + 12, minute)
    if hour == 12:
        return _fmt(12, minute), 0.55, "12 with no period", (_fmt(0, minute),)
    likely, other = (pm, am) if hour <= 6 else (am, pm)
    return likely, 0.55, "no part of the day given", (other,)


def _period_near(tokens: list[Token], first: int, last: int, lex: TimeDateLexicon) -> str | None:
    """Nearest period word before ``first`` or after ``last`` (skipping filler words)."""
    for step, index in ((-1, first - 1), (1, last + 1)):
        taken = 0
        while 0 <= index < len(tokens) and taken < _PERIOD_RADIUS:
            word = tokens[index].norm
            if word in lex.periods:
                return lex.periods[word]
            if tokens[index].kind == "word" and word not in lex.fillers and word not in lex.baje:
                break
            index += step
            taken += 1
    return None


def _index_at(tokens: list[Token], offset: int, *, end: bool = False) -> int:
    for i, token in enumerate(tokens):
        if (token.end >= offset) if end else (token.start >= offset):
            return i
    return len(tokens)


def _resolve(
    tokens: list[Token],
    start: int,
    end: int,
    hour: int,
    minute: int,
    ampm: str | None,
    lex: TimeDateLexicon,
) -> TimeMatch | None:
    if not (0 <= hour <= 24 and 0 <= minute < 60):
        return None
    first, last = _index_at(tokens, start), _index_at(tokens, end, end=True)
    if ampm and 1 <= hour <= 12:
        value, conf, why = _from_ampm(hour, minute, ampm)
        return TimeMatch(value, start, end, conf, why)
    if hour == 24:
        hour = 0
    if hour >= 13 or hour == 0:
        value, conf, why, alts = _bare(hour, minute)
        return TimeMatch(value, start, end, conf, why, alts)
    period = _period_near(tokens, first, last, lex)
    if period:
        resolved = _from_period(hour, minute, period)
        if resolved:
            value, conf, why = resolved
            return TimeMatch(value, start, end, conf, f"{why} cue")
    value, conf, why, alts = _bare(hour, minute)
    return TimeMatch(value, start, end, conf, why, alts)


def _word_clock(text: str, tokens: list[Token], lex: TimeDateLexicon) -> list[TimeMatch]:
    out: list[TimeMatch] = []
    numbers = find_numbers(text)
    for k, m in enumerate(numbers):
        nxt = _index_at(tokens, m.end)
        if nxt >= len(tokens):
            continue
        value = float(m.value)
        hour, fraction = int(value), value - int(value)
        minute = round(fraction * 60)
        end_token = nxt
        follower = tokens[nxt].norm
        # "aath paintalis baje" (8:45): hour, then minutes spoken as a number, then baje
        if follower not in lex.baje and k + 1 < len(numbers) and fraction == 0:
            after = numbers[k + 1]
            tail = _index_at(tokens, after.end)
            if (
                1 <= hour <= 12
                and after.start - m.end <= 2
                and float(after.value) == int(after.value)
                and 1 <= int(after.value) <= 59
                and tail < len(tokens)
                and tokens[tail].norm in lex.baje
            ):
                minute, end_token, follower = int(after.value), tail, tokens[tail].norm
        # "char bajkar tees minute" (4:30): hour, baje, minutes, the word minute
        elif follower in lex.baje and k + 1 < len(numbers) and fraction == 0:
            after = numbers[k + 1]
            tail = _index_at(tokens, after.end)
            if (
                1 <= hour <= 12
                and float(after.value) == int(after.value)
                and 1 <= int(after.value) <= 59
                and tail < len(tokens)
                and tokens[tail].norm in lex.minutes
                and after.start >= tokens[nxt].end
                and after.start - tokens[nxt].end <= 2
            ):
                minute, end_token = int(after.value), tail
        if follower not in lex.baje:
            tail_match = _AMPM_TAIL.match(text, m.end)
            if tail_match and fraction == 0 and 1 <= hour <= 12:
                found = _resolve(
                    tokens, m.start, tail_match.end(), hour, 0, tail_match.group("ampm"), lex
                )
                if found:
                    out.append(found)
            continue
        if abs(fraction * 60 - round(fraction * 60)) > 1e-6 or (
            end_token == nxt and minute not in (0, 15, 30, 45)
        ):
            continue
        # a fraction of 0.5 means "half past": dedh baje is 1:30, saade nau baje is 9:30
        match = _resolve(tokens, m.start, tokens[end_token].end, hour, minute, None, lex)
        if match:
            out.append(match)
    return out


def _numeric_clock(text: str, tokens: list[Token], lex: TimeDateLexicon) -> list[TimeMatch]:
    out: list[TimeMatch] = []
    for pattern in (_COLON, _DOT_MARKED, _HOUR_AMPM):
        for m in pattern.finditer(text):
            groups = m.groupdict()
            minute = int(groups["m"]) if groups.get("m") else 0
            tail = text[m.end() :]
            end = m.end()
            baje_after = re.match(r"\s*(baje|बजे)", tail, re.I)
            if baje_after and not groups.get("ampm"):
                end += baje_after.end()
            hour = int(groups["h"])
            match = _resolve(tokens, m.start(), end, hour, minute, groups.get("ampm"), lex)
            colon_24 = (
                pattern is _COLON
                and not groups.get("ampm")
                and (groups["h"].startswith("0") or hour >= 10)
            )
            if match and colon_24 and match.confidence < 0.6:
                # "09:30" and "10:45" are 24-hour notation unless a part of the day says otherwise
                own = _fmt(hour, minute)
                other = tuple(a for a in (match.value, *match.alternatives) if a != own)
                match = TimeMatch(own, match.start, match.end, 0.85, "24-hour notation", other)
            if match:
                out.append(match)
    return out


def find_times(text: str) -> list[TimeMatch]:
    """Every clock time in ``text``, left to right, with spans."""
    lex = time_date_lexicon()
    tokens = tokenize(text)
    candidates = _numeric_clock(text, tokens, lex) + _word_clock(text, tokens, lex)
    # digit-plus-baje ("9 baje") is read by the word path, so drop numeric duplicates inside it
    candidates.sort(key=lambda t: (t.start, -(t.end - t.start)))
    kept: list[TimeMatch] = []
    for cand in candidates:
        if kept and cand.start < kept[-1].end:
            continue
        kept.append(cand)
    return kept


def parse_time(text: str) -> Canonicalized | None:
    """The first clock time in ``text`` as "HH:MM"; None if there is none."""
    times = find_times(text)
    return times[0].canonicalized() if times else None


def find_durations(text: str) -> list[DurationMatch]:
    """Durations in minutes: "pandrah minute" is 15, "dedh ghante" is 90, "आधे घंटे" is 30."""
    lex = time_date_lexicon()
    tokens = tokenize(text)
    out: list[DurationMatch] = []
    for m in find_numbers(text):
        nxt = _index_at(tokens, m.end)
        if nxt >= len(tokens):
            continue
        unit = tokens[nxt].norm
        if unit in lex.minutes:
            minutes: float = float(m.value)
        elif unit in lex.hours:
            minutes = float(m.value) * 60
        else:
            continue
        value: int | float = int(minutes) if minutes == int(minutes) else minutes
        out.append(
            DurationMatch(value, m.start, tokens[nxt].end, m.confidence, f"{m.reason}; {unit}")
        )
    return out


def parse_duration(text: str) -> Canonicalized | None:
    durations = find_durations(text)
    return durations[0].canonicalized() if durations else None


__all__ = [
    "DurationMatch",
    "NumberMatch",
    "TimeMatch",
    "find_durations",
    "find_times",
    "parse_duration",
    "parse_time",
]
