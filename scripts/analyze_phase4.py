"""Analysis of the A7 test run (docs/PREREG.md): T1-T4 plus descriptive tables. Aggregates only.

python scripts/analyze_phase4.py > p4_summary.md
"""

from __future__ import annotations

import statistics
import time
from datetime import date
from pathlib import Path

from harness.compare import load_trials, task_scores
from harness.metrics import paired_bootstrap_ci
from harness.schema import Task, load_tasks

R = Path("harness/reports")
MODELS = ["qwen3.5-4b", "granite-4.0-micro", "ministral-3-3b"]
TEST = Path("harness/tasks/test")
DEV = Path("harness/tasks/dev")


def _select(tasks: list[Task], source: set[str], lang: str | None = None) -> set[str]:
    return {t.id for t in tasks if t.source in source and (lang is None or t.lang == lang)}


def _rate(runs: dict[str, list[dict[str, object]]], ids: list[str], field: str) -> float:
    vals = [bool(r[field]) for i in ids for r in runs[i]]
    return sum(vals) / len(vals)


def _diff(model: str, arm: str, ids: set[str], base: str = "off") -> str:
    a = load_trials(R / f"p4-{model}-{arm}" / "results.jsonl")
    b = load_trials(R / f"p4-{model}-{base}" / "results.jsonl")
    keep = sorted(ids & a.keys() & b.keys())
    if not keep:
        return "n/a"
    m, lo, hi = paired_bootstrap_ci(task_scores(a, keep), task_scores(b, keep))
    return f"{100 * m:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] (n={len(keep)})"


def main() -> None:
    tasks = load_tasks(TEST)
    sets = {
        "value-heavy (all)": _select(tasks, {"value_heavy"}),
        "value-heavy Hinglish": _select(tasks, {"value_heavy"}, "hinglish"),
        "BFCL English": _select(tasks, {"bfcl_en"}),
        "BFCL Hinglish": _select(tasks, {"bfcl_hinglish"}),
        "Hinglish pooled": _select(tasks, {"value_heavy", "bfcl_hinglish"}, "hinglish"),
    }
    print("# A7 test run: paired pass^4 change (points) against `off`\n")
    for arm in ("annotate", "both", "worked"):
        print(f"\n## {arm} - off\n\n| set | " + " | ".join(MODELS) + " |\n|---|---|---|---|")
        for name, ids in sets.items():
            cells = []
            for m in MODELS:
                try:
                    cells.append(_diff(m, arm, ids))
                except FileNotFoundError:
                    cells.append("not run")
            print(f"| {name} | " + " | ".join(cells) + " |")
    try:
        print("\n## Qwen: both minus the better of off and worked, Hinglish pooled (T3)\n")
        ids = sorted(sets["Hinglish pooled"])
        off, wk, both = (
            load_trials(R / f"p4-qwen3.5-4b-{a}" / "results.jsonl")
            for a in ("off", "worked", "both")
        )
        ids = [i for i in ids if i in off and i in wk and i in both]
        so, sw, sb = task_scores(off, ids), task_scores(wk, ids), task_scores(both, ids)
        best = so if sum(so) >= sum(sw) else sw
        m, lo, hi = paired_bootstrap_ci(sb, best)
        print(
            f"both minus best baseline: {100 * m:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] (n={len(ids)}); "
            f"off {100 * sum(so) / len(so):.1f}, worked {100 * sum(sw) / len(sw):.1f}, both {100 * sum(sb) / len(sb):.1f}"
        )
    except FileNotFoundError:
        print("T3 not available yet: an arm has not been run")
    print(
        "\n## Wrong-value and flag rates (all test tasks run)\n\n| model | arm | pass^4 | wrong | flagged |\n|---|---|---|---|---|"
    )
    for m in MODELS:
        for arm in ("off", "annotate", "both", "worked"):
            p = R / f"p4-{m}-{arm}" / "results.jsonl"
            if not p.exists():
                continue
            runs = load_trials(p)
            ids2 = sorted(runs)
            s = task_scores(runs, ids2)
            print(
                f"| {m} | {arm} | {100 * sum(s) / len(s):.1f} | {100 * _rate(runs, ids2, 'wrong_value'):.1f}% | "
                f"{100 * _rate(runs, ids2, 'flagged'):.1f}% |"
            )
    print("\n## T4: added canonicalizer time (dev turns, CPU)\n")
    from vaad.canon import annotate_turn

    turns = [t.user_text() for t in load_tasks(DEV) if t.source == "value_heavy"]
    times = []
    for text in turns * 3:
        t0 = time.perf_counter()
        annotate_turn(text, date(2026, 10, 24))
        times.append((time.perf_counter() - t0) * 1000)
    q = statistics.quantiles(times, n=100)
    print(
        f"annotate_turn over {len(times)} calls: p50 {statistics.median(times):.2f} ms, p95 {q[94]:.2f} ms"
    )


if __name__ == "__main__":
    main()
