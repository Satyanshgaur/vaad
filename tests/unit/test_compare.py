from __future__ import annotations

import pytest

from harness.compare import paired
from harness.schema import Message, Task


def _task(task_id: str, source: str, pair: str) -> Task:
    return Task(
        id=task_id,
        source=source,  # type: ignore[arg-type]
        lang="en" if source == "bfcl_en" else "hinglish",
        pair_id=pair,
        messages=[Message(role="user", content="x")],
        tools=[],
        expected_calls=[],
    )


def _trials(task_id: str, passes: list[bool]) -> list[dict[str, object]]:
    return [{"task_id": task_id, "seed": i, "correct": ok} for i, ok in enumerate(passes)]


@pytest.mark.unit
def test_paired_difference_uses_matched_tasks_only() -> None:
    tasks = {}
    by_task: dict[str, list[dict[str, object]]] = {}
    for i in range(20):
        a, b = _task(f"A{i}", "bfcl_en", f"p{i}"), _task(f"B{i}", "bfcl_hinglish", f"p{i}")
        tasks[a.id], tasks[b.id] = a, b
        by_task[a.id] = _trials(a.id, [True] * 4)
        by_task[b.id] = _trials(b.id, [True, True, True, i % 2 == 0])  # inconsistent half the time
    orphan = _task("A99", "bfcl_en", "p99")  # no B partner: must not count
    tasks[orphan.id] = orphan
    by_task[orphan.id] = _trials(orphan.id, [False] * 4)

    result = paired(by_task, tasks, "bfcl_en", "bfcl_hinglish")
    assert result["pairs"] == 20
    mean, low, high = result["diff_b_minus_a"]
    assert mean == pytest.approx(-0.5)
    assert high < 0  # the CI excludes zero
    assert low <= mean <= high
