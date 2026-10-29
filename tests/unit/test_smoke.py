from __future__ import annotations

from collections import Counter

import pytest

from harness.schema import Message, Task
from harness.smoke import N_TASKS, compare, select_tasks


def _tasks() -> list[Task]:
    out = []
    for source, lang, count in (
        ("bfcl_en", "en", 30),
        ("bfcl_hi", "hi", 30),
        ("bfcl_hinglish", "hinglish", 8),
    ):
        for i in range(count):
            out.append(
                Task(
                    id=f"{source}:{i}",
                    source=source,
                    lang=lang,
                    pair_id=f"p:{source}:{i}",
                    messages=[Message(role="user", content="x")],
                    tools=[],
                    expected_calls=[],
                )
            )
    return out


@pytest.mark.unit
def test_selection_is_deterministic_and_balanced() -> None:
    tasks = _tasks()
    first, second = select_tasks(tasks), select_tasks(list(reversed(tasks)))
    assert [t.id for t in first] == [t.id for t in second]
    assert len(first) == N_TASKS
    counts = Counter(t.source for t in first)
    assert counts["bfcl_hinglish"] == 8  # the small group is exhausted, the rest share evenly
    assert abs(counts["bfcl_en"] - counts["bfcl_hi"]) <= 1


@pytest.mark.unit
def test_compare_allows_noise_but_not_a_collapse() -> None:
    assert compare(0.85, 0.90)
    assert compare(0.80, 0.90)
    assert not compare(0.60, 0.90)
