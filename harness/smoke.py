"""Gate 9: a tiny-model smoke eval that catches a broken request path, not a quality change.

Runs a fixed 50-task slice of the dev split once (seed 0, temperature 0) against a
llama-server and compares the schema-valid rate to ``harness/reports/smoke_baseline.json``.

    python -m harness.smoke --base-url http://127.0.0.1:8080            # check
    python -m harness.smoke --base-url http://127.0.0.1:8080 --write-baseline
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from harness.run import Condition, run_grid
from harness.schema import Task, load_tasks

DEV_DIR = Path("harness/tasks/dev")
BASELINE = Path("harness/reports/smoke_baseline.json")
N_TASKS = 50
SEED = 20261029
# A 0.8B model is noisy, so only a clear drop in schema-valid output fails the gate.
TOLERANCE = 0.10
MODEL, QUANT = "qwen3.5-0.8b", "Q8_0"


def select_tasks(tasks: list[Task], n: int = N_TASKS, seed: int = SEED) -> list[Task]:
    """A deterministic slice spread evenly over every source and language."""
    groups: dict[str, list[Task]] = defaultdict(list)
    for task in sorted(tasks, key=lambda t: t.id):
        groups[f"{task.source}:{task.lang}"].append(task)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    picked: list[Task] = []
    while len(picked) < n and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(picked) < n:
                picked.append(groups[key].pop())
    return sorted(picked, key=lambda t: t.id)


def compare(rate: float, baseline: float, tolerance: float = TOLERANCE) -> bool:
    return rate >= baseline - tolerance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.smoke")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)

    tasks = select_tasks(load_tasks(DEV_DIR))
    condition = Condition(
        model=MODEL,
        quant=QUANT,
        gateway="off",
        base_url=args.base_url.rstrip("/"),
        extra={"chat_template_kwargs": {"enable_thinking": False}},
    )
    with tempfile.TemporaryDirectory() as tmp:
        results = run_grid(tasks, [condition], Path(tmp), seeds=(0,), temperature=0.0)
    schema_valid = sum(r.schema_valid for r in results) / len(results)
    correct = sum(r.correct for r in results) / len(results)
    print(f"smoke: {len(results)} trials, schema-valid {schema_valid:.2f}, correct {correct:.2f}")

    if args.write_baseline:
        record = {
            "model": MODEL,
            "quant": QUANT,
            "tasks": len(results),
            "schema_valid": round(schema_valid, 4),
            "correct": round(correct, 4),
            "tolerance": TOLERANCE,
        }
        args.baseline.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.baseline}")
        return 0
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["schema_valid"]
    if not compare(schema_valid, baseline):
        print(f"FAIL: schema-valid {schema_valid:.2f} < baseline {baseline:.2f} - {TOLERANCE}")
        return 1
    print(f"ok: within {TOLERANCE} of baseline {baseline:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
