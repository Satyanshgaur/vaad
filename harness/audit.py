"""Build the human-audit sheet for field-aware rescoring (docs/PREREG.md, H2 rule 4).

Picks free-text and name comparisons the exact scorer rejects, samples them around the decision
threshold, and writes two files: the sheet a native speaker fills in (no similarity, no rule
decision, so the label is not biased) and a key that maps rows back to them.

    python -m harness.audit --runs name=dir ... --embed-url http://127.0.0.1:8200 \\
        --out private/review
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

from harness.rescore import (
    DEFAULT_TAU,
    Embedder,
    digits_preserved,
    field_classes,
    names_equal,
)
from harness.schema import Task, load_tasks
from harness.score import values_equal

SEED = 20261030


def candidates(
    runs: dict[str, Path], tasks: dict[str, Task], embedder: Embedder
) -> list[dict[str, Any]]:
    """Unique (task, field, predicted, expected) pairs that exact matching rejects."""
    seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for model, directory in runs.items():
        for line in (directory / "results.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            task = tasks[row["task_id"]]
            if task.source not in ("bfcl_hi", "bfcl_en", "bfcl_hinglish"):
                continue
            if len(task.expected_calls) != 1 or len(row["predicted"]) != 1:
                continue
            expected = task.expected_calls[0]
            if row["predicted"][0]["name"] != expected.name:
                continue
            classes = field_classes(task)
            for arg, acceptable in expected.arguments.items():
                value = row["predicted"][0]["arguments"].get(arg)
                if (
                    not isinstance(value, str)
                    or not acceptable
                    or not isinstance(acceptable[0], str)
                    or any(values_equal(value, a) for a in acceptable)
                ):
                    continue
                cls = classes.get(arg, "identifier")
                if cls == "identifier":
                    continue
                key = (task.id, arg, value, acceptable[0])
                if key in seen:
                    continue
                if cls == "free_text":
                    if not digits_preserved(value, acceptable[0]):
                        continue
                    sim = embedder.similarity(value, acceptable[0])
                    accepted = sim >= DEFAULT_TAU
                else:
                    sim = embedder.similarity(value, acceptable[0])
                    accepted = names_equal(value, acceptable[0])
                seen[key] = {
                    "task_id": task.id, "lang": task.lang, "field": arg, "class": cls,
                    "expected": acceptable[0], "predicted": value, "similarity": round(sim, 3),
                    "accepted": accepted, "model": model,
                }  # fmt: skip
    return list(seen.values())


def sample(cands: list[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    """About 20 free-text just above tau, 20 just below, 10 random, and up to 10 names."""
    rng = random.Random(seed)
    free = [c for c in cands if c["class"] == "free_text"]
    names = [c for c in cands if c["class"] == "name"]
    above = sorted((c for c in free if c["accepted"]), key=lambda c: c["similarity"])
    below = sorted((c for c in free if not c["accepted"]), key=lambda c: -c["similarity"])
    picked = above[:20] + below[:20]
    rest = [c for c in free if c not in picked]
    picked += rng.sample(rest, min(10, len(rest)))
    picked += rng.sample(names, min(10, len(names)))
    rng.shuffle(picked)
    return picked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.audit")
    parser.add_argument("--runs", nargs="+", required=True, help="name=run directory")
    parser.add_argument("--tasks", type=Path, default=Path("harness/tasks/dev"))
    parser.add_argument("--embed-url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = {s.partition("=")[0]: Path(s.partition("=")[2]) for s in args.runs}
    tasks = {t.id: t for t in load_tasks(args.tasks)}
    embedder = Embedder(args.embed_url)
    picked = sample(candidates(runs, tasks, embedder))
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "rescore_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "field_kind", "expected (answer key)", "model output",
                    "equivalent? (yes / no)", "comment", "reviewer"])  # fmt: skip
        for i, c in enumerate(picked, 1):
            kind = "name" if c["class"] == "name" else "free text"
            w.writerow([i, kind, c["expected"], c["predicted"], "", "", ""])
    with (args.out / "rescore_audit_key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "task_id", "model", "field", "class", "similarity", "rule_accepts"])
        for i, c in enumerate(picked, 1):
            w.writerow([i, c["task_id"], c["model"], c["field"], c["class"], c["similarity"],
                        c["accepted"]])  # fmt: skip
    print(f"{len(picked)} rows -> {args.out}/rescore_audit.csv (+ key)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
