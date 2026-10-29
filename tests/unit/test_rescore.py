from __future__ import annotations

from typing import Any

import pytest

from harness.rescore import (
    classify_field,
    digits_preserved,
    make_matcher,
    names_equal,
    phonetic_key,
)
from harness.schema import ExpectedCall, Message, Task, ToolCall
from harness.score import calls_match


def _task(props: dict[str, dict[str, Any]], expected: dict[str, list[Any]]) -> Task:
    return Task(
        id="bfcl_hi:x",
        source="bfcl_hi",
        lang="hi",
        pair_id="bfcl:x",
        messages=[Message(role="user", content="x")],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "f",
                    "parameters": {"type": "object", "properties": props},
                },
            }
        ],
        expected_calls=[ExpectedCall(name="f", arguments=expected)],
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "prop", "expected"),
    [
        ("content", {"type": "string", "description": "The task text."}, "free_text"),
        ("Title", {"type": "string"}, "free_text"),
        ("new_alarm_name", {"type": "string", "description": "The label"}, "free_text"),
        ("UrlName", {"type": "string", "description": "The URL-friendly name"}, "identifier"),
        (
            "query",
            {"type": "string", "description": "formatted as 'track:X artist:Y'"},
            "identifier",
        ),
        ("date", {"type": "string", "description": "format 'YYYY-MM-DD'"}, "identifier"),
        ("city", {"type": "string", "description": "in the format of 'City, State'"}, "name"),
        ("artist", {"type": "string"}, "name"),
        ("unit", {"type": "string", "enum": ["a", "b"]}, "identifier"),
        ("count", {"type": "integer"}, "identifier"),
        ("color", {"type": "string"}, "identifier"),  # unplaceable: strict
        ("command", {"type": "string", "description": "The system command"}, "identifier"),
    ],
)
def test_field_classes(name: str, prop: dict[str, Any], expected: str) -> None:
    assert classify_field(name, prop) == expected


@pytest.mark.unit
def test_digits_must_survive() -> None:
    assert digits_preserved("रात ९ बजे सोना", "call the plumber at 9 pm")
    assert not digits_preserved("रात को सोना", "call the plumber at 9 pm")
    assert digits_preserved("anything", "no numbers here")


@pytest.mark.unit
def test_names_accept_transliteration_but_not_different_names() -> None:
    assert names_equal("जूलियन", "Julian")
    assert names_equal("बोस्टन", "Boston")
    assert names_equal("boston", "Boston")
    assert not names_equal("मुंबई", "Delhi")
    assert phonetic_key("") == ""


@pytest.mark.unit
def test_free_text_needs_similarity_and_digits() -> None:
    task = _task({"content": {"type": "string"}}, {"content": ["call the plumber at 9 pm"]})
    always = make_matcher(task, lambda a, b: 0.95)
    never = make_matcher(task, lambda a, b: 0.1)
    hindi = ToolCall(name="f", arguments={"content": "रात 9 बजे शॉपिंग पर जाएं"})
    wrong_number = ToolCall(name="f", arguments={"content": "रात 8 बजे शॉपिंग पर जाएं"})
    assert calls_match([hindi], task.expected_calls, always)
    assert not calls_match([hindi], task.expected_calls, never)
    assert not calls_match([wrong_number], task.expected_calls, always)
    assert not calls_match([hindi], task.expected_calls)  # exact scoring still rejects it


@pytest.mark.unit
def test_identifiers_stay_exact_whatever_the_similarity() -> None:
    task = _task(
        {"UrlName": {"type": "string", "description": "The URL-friendly name"}},
        {"UrlName": ["julian-testing"]},
    )
    match = make_matcher(task, lambda a, b: 1.0)
    bad = ToolCall(name="f", arguments={"UrlName": "जूलियन-टेस्टिंग"})
    assert not calls_match([bad], task.expected_calls, match)


@pytest.mark.unit
def test_exact_matches_are_unchanged() -> None:
    task = _task({"n": {"type": "number"}}, {"n": [2]})
    assert calls_match(
        [ToolCall(name="f", arguments={"n": 2.0})],
        task.expected_calls,
        make_matcher(task, lambda a, b: 0.0),
    )
