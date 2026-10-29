"""Per-set breakdown, the Devanagari-in-free-text diagnostic and paired model comparisons.

    python -m harness.breakdown --run qwen=harness/reports/f1-qwen3.5-4b-Q4_K_M/raw \\
        --run granite=harness/reports/f1-granite-4.0-micro-Q4_K_M/raw

Sets are never pooled: BFCL and value-heavy are reported separately for every language.
Rescored columns need ``results_fieldaware.jsonl`` (``python -m harness.rescore``) and are
exploratory until the human audit in docs/PREREG.md is done.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from harness.compare import load_trials, task_scores
from harness.metrics import bootstrap_ci, paired_bootstrap_ci
from harness.rescore import field_classes
from harness.schema import Task, load_tasks
from harness.score import values_equal

SETS = (
    ("BFCL", "bfcl_en", "en"),
    ("BFCL", "bfcl_hi", "hi"),
    ("BFCL", "bfcl_hinglish", "hinglish"),
    ("value-heavy", "value_heavy", "en"),
    ("value-heavy", "value_heavy", "hi"),
    ("value-heavy", "value_heavy", "hinglish"),
)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
Runs = dict[str, dict[str, list[dict[str, Any]]]]


def ids_of(tasks: dict[str, Task], source: str, lang: str) -> list[str]:
    return sorted(i for i, t in tasks.items() if t.source == source and t.lang == lang)


def fmt(ci: tuple[float, float, float], signed: bool = False) -> str:
    sign = "+" if signed else ""
    return f"{ci[0] * 100:{sign}.1f} [{ci[1] * 100:{sign}.1f}, {ci[2] * 100:{sign}.1f}]"


def per_set_table(runs: Runs, tasks: dict[str, Task], field: str = "correct") -> list[str]:
    lines = ["| Set | Language | Tasks | " + " | ".join(f"{n} pass^4" for n in runs) + " |"]
    lines.append("|---|---|---|" + "---|" * len(runs))
    for label, source, lang in SETS:
        ids = ids_of(tasks, source, lang)
        cells = [fmt(bootstrap_ci(task_scores(by, ids, field=field))) for by in runs.values()]
        lines.append(f"| {label} | {lang} | {len(ids)} | " + " | ".join(cells) + " |")
    return lines


def devanagari_diagnostic(
    by_task: dict[str, list[dict[str, Any]]], tasks: dict[str, Task], source: str = "bfcl_hi"
) -> Counter[str]:
    """Classify every mismatched string argument of single-call Hindi tasks."""
    out: Counter[str] = Counter()
    for task_id, trials in by_task.items():
        task = tasks.get(task_id)
        if task is None or task.source != source or len(task.expected_calls) != 1:
            continue
        classes = field_classes(task)
        expected = task.expected_calls[0]
        for trial in trials:
            if len(trial["predicted"]) != 1 or trial["predicted"][0]["name"] != expected.name:
                continue
            given = trial["predicted"][0]["arguments"]
            for arg, acceptable in expected.arguments.items():
                if arg not in given or not acceptable or not isinstance(acceptable[0], str):
                    continue
                value = given[arg]
                if any(values_equal(value, a) for a in acceptable):
                    continue
                text = value if isinstance(value, str) else str(value)
                dev = bool(_DEVANAGARI.search(text)) and not _DEVANAGARI.search(str(acceptable[0]))
                kind = classes.get(arg, "identifier")
                key = f"Devanagari kept, {kind}" if dev else f"other mismatch, {kind}"
                out[key] += 1
    return out


def paired_models(
    a: dict[str, list[dict[str, Any]]],
    b: dict[str, list[dict[str, Any]]],
    ids: list[str],
    field_a: str,
    field_b: str,
) -> tuple[float, float, float]:
    """Mean per-task pass^4 of A minus B on the same tasks."""
    return paired_bootstrap_ci(
        task_scores(a, ids, field=field_a), task_scores(b, ids, field=field_b)
    )


def load_runs(specs: list[str], filename: str) -> Runs:
    runs: Runs = {}
    for spec in specs:
        name, _, path = spec.partition("=")
        runs[name] = load_trials(Path(path) / filename)
    return runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.breakdown")
    parser.add_argument("--run", action="append", required=True, help="name=run directory")
    parser.add_argument("--tasks", type=Path, default=Path("harness/tasks/dev"))
    args = parser.parse_args(argv)
    tasks = {t.id: t for t in load_tasks(args.tasks)}
    raw = load_runs(args.run, "results.jsonl")
    names = list(raw)

    print("## 1. Per-set pass^4 (raw scoring), mean [95% CI over tasks], points\n")
    print("\n".join(per_set_table(raw, tasks)))

    print("\n## 2. Hindi string mismatches (BFCL-Hi, single-call tasks, all seeds)\n")
    print("| Kind | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    diag = {n: devanagari_diagnostic(raw[n], tasks) for n in names}
    kinds = sorted({k for d in diag.values() for k in d})
    for kind in kinds:
        print(f"| {kind} | " + " | ".join(str(diag[n][kind]) for n in names) + " |")
    print(
        "| **total mismatches** | " + " | ".join(str(sum(diag[n].values())) for n in names) + " |"
    )
    print(
        "| **share: Devanagari kept in free text** | "
        + " | ".join(
            f"{diag[n]['Devanagari kept, free_text'] / max(1, sum(diag[n].values())):.0%}"
            for n in names
        )
        + " |"
    )

    try:
        fa = load_runs(args.run, "results_fieldaware.jsonl")
    except FileNotFoundError:
        print("\n(no results_fieldaware.jsonl: run harness.rescore for sections 3 and 4)")
        return 0
    print("\n## 3. Field-aware rescored pass^4 (exploratory, tau fixed, unaudited)\n")
    print("\n".join(per_set_table(fa, tasks, "correct_fieldaware")))
    print("\nRescored minus raw, paired per task (points):\n")
    print("| Set | Language | " + " | ".join(names) + " |\n|---|---|" + "---|" * len(names))
    for label, source, lang in SETS:
        ids = ids_of(tasks, source, lang)
        cells = [
            fmt(paired_models(fa[n], raw[n], ids, "correct_fieldaware", "correct"), True)
            for n in names
        ]
        print(f"| {label} | {lang} | " + " | ".join(cells) + " |")

    if len(names) >= 2:
        a, b = names[0], names[1]
        print(f"\n## 4. {a} minus {b}, paired on the same tasks (points)\n")
        print("| Set | Language | Tasks | raw | rescored |\n|---|---|---|---|---|")
        for label, source, lang in SETS:
            ids = ids_of(tasks, source, lang)
            r = paired_models(raw[a], raw[b], ids, "correct", "correct")
            s = paired_models(fa[a], fa[b], ids, "correct_fieldaware", "correct_fieldaware")
            print(f"| {label} | {lang} | {len(ids)} | {fmt(r, True)} | {fmt(s, True)} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
