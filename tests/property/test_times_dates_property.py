"""Gates 5 and 6 for times, durations and dates: round trips, direction cues, spans."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vaad.canon.dates import find_dates, parse_date
from vaad.canon.times import find_durations, find_times, parse_time

REFS = st.dates(min_value=date(2024, 1, 1), max_value=date(2030, 12, 31))
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]  # fmt: skip
WEEKDAYS = ["somvaar", "mangalvaar", "budhvaar", "guruvaar", "shukravaar", "shanivaar", "ravivaar"]


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(st.integers(1, 12), st.sampled_from([0, 15, 30, 45]), st.sampled_from(["am", "pm"]))
def test_am_pm_round_trip(hour: int, minute: int, ampm: str) -> None:
    got = parse_time(f"{hour}:{minute:02d} {ampm}")
    expected = hour % 12 + (12 if ampm == "pm" else 0)
    assert got is not None and got.value == f"{expected:02d}:{minute:02d}"
    assert got.confidence >= 0.9


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(st.integers(0, 23), st.integers(0, 59))
def test_24_hour_round_trip(hour: int, minute: int) -> None:
    got = parse_time(f"{hour:02d}:{minute:02d}")
    assert got is not None and got.value == f"{hour:02d}:{minute:02d}"


PERIOD_HOURS = [("subah", range(1, 12), 0), ("dopahar", range(1, 7), 12),
                ("shaam", range(4, 12), 12), ("raat", range(6, 12), 12)]  # fmt: skip


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(st.sampled_from(PERIOD_HOURS), st.data(), st.sampled_from([0, 15, 30, 45]))
def test_period_word_settles_am_or_pm(
    period: tuple[str, range, int], data: st.DataObject, minute: int
) -> None:
    word, hours, offset = period
    hour = data.draw(st.sampled_from(list(hours)))
    got = parse_time(f"{word} {hour}:{minute:02d} baje")
    assert got is not None
    assert got.value == f"{hour + offset:02d}:{minute:02d}"
    assert got.confidence >= 0.9


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(st.integers(1, 11), st.sampled_from(["baje"]))
def test_a_bare_hour_is_never_confident(hour: int, word: str) -> None:
    got = parse_time(f"{hour} {word}")
    assert got is not None and got.confidence < 0.6  # AM or PM: the decision layer must ask


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(st.integers(1, 59), st.sampled_from(["minute", "ghante"]))
def test_durations_round_trip(n: int, unit: str) -> None:
    durations = find_durations(f"{n} {unit}")
    assert len(durations) == 1
    assert durations[0].minutes == (n if unit == "minute" else n * 60)


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(REFS)
def test_iso_dates_round_trip(day: date) -> None:
    got = parse_date(day.isoformat(), date(2026, 10, 24))
    assert got is not None and got.value == day.isoformat() and got.confidence == 1.0


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(REFS, st.integers(1, 400), st.sampled_from(["baad", "pehle"]))
def test_day_offsets(ref: date, n: int, direction: str) -> None:
    got = parse_date(f"{n} din {direction}", ref)
    sign = 1 if direction == "baad" else -1
    assert got is not None and got.value == (ref + timedelta(days=sign * n)).isoformat()


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(REFS, st.integers(1, 28), st.integers(1, 12))
def test_day_and_month_look_forward(ref: date, day: int, month: int) -> None:
    got = parse_date(f"{day} {MONTHS[month - 1]}", ref)
    assert got is not None
    resolved = date.fromisoformat(got.value)
    assert (resolved.month, resolved.day) == (month, day)
    assert resolved >= ref  # no year given and no past cue: the next occurrence


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(REFS, st.sampled_from(WEEKDAYS))
def test_next_and_last_weekday(ref: date, name: str) -> None:
    weekday = WEEKDAYS.index(name)
    nxt, last = parse_date(f"agle {name}", ref), parse_date(f"pichhle {name}", ref)
    assert nxt is not None and last is not None
    n, p = date.fromisoformat(nxt.value), date.fromisoformat(last.value)
    assert n.weekday() == weekday and p.weekday() == weekday
    assert 1 <= (n - ref).days <= 7 and 1 <= (ref - p).days <= 7


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(REFS, st.sampled_from(["karo", "lagao", "hoga", "rahega", "bhejo"]),
       st.sampled_from(["tha", "thi", "the", "suna"]))  # fmt: skip
def test_kal_follows_the_tense_cue(ref: date, future: str, past: str) -> None:
    ahead, behind = parse_date(f"kal mausam {future}", ref), parse_date(f"kal mausam {past}", ref)
    assert ahead is not None and ahead.value == (ref + timedelta(days=1)).isoformat()
    assert behind is not None and behind.value == (ref - timedelta(days=1)).isoformat()


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(REFS)
def test_kal_with_no_cue_is_flagged_not_guessed(ref: date) -> None:
    got = parse_date("kal", ref)
    assert got is not None and got.confidence < 0.6
    assert "also possible" in got.reason  # both readings are offered


WORDS = ["mera", "order", "bhej", "mausam", "batao", "delivery", "payment", "aur", "ka", "hai",
         "भेज", "मौसम", "ऑर्डर", "बताओ", "का", "है", "2", "5", "kilo", "rupaye"]  # fmt: skip
DATE_TIME_WORDS = ["kal", "parson", "aaj", "baje", "subah", "shaam", "agle", "somvaar", "March",
                   "12", "15 tarikh", "teen din baad"]  # fmt: skip


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(st.lists(st.sampled_from(WORDS), max_size=12))
def test_text_without_date_or_time_words_has_none(words: list[str]) -> None:
    text = " ".join(words)
    assert find_times(text) == []
    assert find_dates(text, date(2026, 10, 24)) == []


@pytest.mark.property
@settings(max_examples=300, deadline=None)
@given(st.lists(st.sampled_from(WORDS + DATE_TIME_WORDS), max_size=14))
def test_spans_stay_inside_the_text_and_do_not_overlap(tokens: list[str]) -> None:
    text = " ".join(tokens)
    for finder in (find_times, lambda t: find_dates(t, date(2026, 10, 24))):
        last = 0
        for m in finder(text):
            assert 0 <= m.start < m.end <= len(text) and m.start >= last
            assert 0.0 < m.confidence <= 1.0
            last = m.end
