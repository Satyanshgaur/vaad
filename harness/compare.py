"""Paired language comparisons on matched tasks, from stored results.

For each pair of languages, tasks are matched on ``pair_id`` and the per-task pass^k
difference gets a bootstrap CI over tasks (``metrics.paired_bootstrap_ci``).

    python -m harness.compare harness/reports/<run>/results.jsonl [more results.jsonl ...]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from harness.metrics import bootstrap_ci, paired_bootstrap_ci, per_task_scores
from harness.schema import Task, load_tasks

DEV = Path("harness/tasks/dev")


def load_trials(path: Path) -> dict[str, list[dict[str, object]]]:
    by_task: dict[str, list[dict[str, object]]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            by_task[row["task_id"]].append(row)
    return by_task


def task_scores(
    by_task: dict[str, list[dict[str, object]]], ids: list[str], k: int = 4, field: str = "correct"
) -> list[float]:
    trials = [
        [bool(t[field]) for t in sorted(by_task[i], key=lambda t: int(str(t["seed"])))] for i in ids
    ]
    return per_task_scores(trials, k)


def matched_ids(
    tasks: dict[str, Task], source_a: str, source_b: str, have: set[str]
) -> list[tuple[str, str]]:
    """(task id in A, task id in B) for pair_ids present in both sources and in the results."""
    a = {t.pair_id: t.id for t in tasks.values() if t.source == source_a}
    b = {t.pair_id: t.id for t in tasks.values() if t.source == source_b}
    return [(a[p], b[p]) for p in sorted(a.keys() & b.keys()) if a[p] in have and b[p] in have]


def paired(
    by_task: dict[str, list[dict[str, object]]],
    tasks: dict[str, Task],
    source_a: str,
    source_b: str,
    k: int = 4,
    field: str = "correct",
) -> dict[str, Any]:
    """B minus A on matched tasks: the CI excludes 0 when the gap is real."""
    pairs = matched_ids(tasks, source_a, source_b, set(by_task))
    sa = task_scores(by_task, [p[0] for p in pairs], k, field)
    sb = task_scores(by_task, [p[1] for p in pairs], k, field)
    return {
        "pairs": len(pairs),
        "a": bootstrap_ci(sa),
        "b": bootstrap_ci(sb),
        "diff_b_minus_a": paired_bootstrap_ci(sb, sa),
    }


COMPARISONS = (
    ("bfcl_en", "bfcl_hinglish", "BFCL Hinglish - English"),
    ("bfcl_en", "bfcl_hi", "BFCL Hindi - English"),
    ("value_heavy:en", "value_heavy:hinglish", "value-heavy Hinglish - English"),
    ("value_heavy:en", "value_heavy:hi", "value-heavy Hindi - English"),
)


def _fmt(ci: tuple[float, float, float]) -> str:
    mean, lo, hi = ci
    return f"{mean:+.3f} [{lo:+.3f}, {hi:+.3f}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.compare")
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--tasks", type=Path, default=DEV)
    parser.add_argument("--field", default="correct")
    args = parser.parse_args(argv)
    tasks = {t.id: t for t in load_tasks(args.tasks)}
    for path in args.results:
        by_task = load_trials(path)
        print(f"== {path.parent.parent.name}/{path.parent.name}")
        for a, b, label in COMPARISONS:
            view = _view(tasks, a, b)
            r = paired(by_task, view, "A", "B", field=args.field)
            print(f"  {label:34s} pairs {r['pairs']:3d}  pass^4 diff {_fmt(r['diff_b_minus_a'])}")
    return 0


def _view(tasks: dict[str, Task], a: str, b: str) -> dict[str, Task]:
    """The tasks of both sides, relabelled as sources 'A' and 'B' (value-heavy sides are
    languages of one source)."""
    out: dict[str, Task] = {}
    for t in tasks.values():
        for side, spec in (("A", a), ("B", b)):
            source, _, lang = spec.partition(":")
            if t.source == source and (not lang or t.lang == lang):
                out[t.id] = t.model_copy(update={"source": side})
    return out


if __name__ == "__main__":
    raise SystemExit(main())
