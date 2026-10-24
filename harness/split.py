"""Deterministic dev/test split, frozen by a lock file.

Splitting is on ``pair_id`` so a task and its Hindi/Hinglish versions always land together;
otherwise the dev set would leak test tasks in another language.

    python -m harness.split assign raw/ harness/tasks/   # write dev/ and test/ files
    python -m harness.split lock harness/tasks/          # write SPLITS.lock
    python -m harness.split check harness/tasks/         # fail if anything changed
    python -m harness.split check harness/tasks/ --allow-missing test/   # CI: test is private
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal

from harness.schema import Task, load_tasks

DEV_FRACTION = 0.4
SALT = "vaad-split-v1"  # Changing this reshuffles everything; never change after G0.
LOCK_NAME = "SPLITS.lock"

Split = Literal["dev", "test"]


def assign(pair_id: str, dev_fraction: float = DEV_FRACTION) -> Split:
    digest = hashlib.sha256(f"{SALT}:{pair_id}".encode()).digest()
    bucket = int.from_bytes(digest[:8], "big") / 2**64
    return "dev" if bucket < dev_fraction else "test"


def split_tasks(tasks: list[Task]) -> dict[Split, list[Task]]:
    out: dict[Split, list[Task]] = {"dev": [], "test": []}
    for t in tasks:
        out[assign(t.pair_id)].append(t)
    return out


def write_split(src: Path, tasks_root: Path) -> None:
    """Write each source file's tasks into tasks_root/{dev,test}/<same name>."""
    files = sorted(src.rglob("*.jsonl")) if src.is_dir() else [src]
    for file in files:
        for name, tasks in split_tasks(load_tasks(file)).items():
            out = tasks_root / name / file.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                "".join(t.model_dump_json(exclude_none=True) + "\n" for t in tasks),
                encoding="utf-8",
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_lock(tasks_root: Path) -> dict[str, object]:
    files = {
        str(p.relative_to(tasks_root)): {"sha256": _sha256(p), "tasks": len(load_tasks(p))}
        for p in sorted(tasks_root.glob("*/*.jsonl"))
    }
    return {"salt": SALT, "dev_fraction": DEV_FRACTION, "files": files}


def write_lock(tasks_root: Path) -> Path:
    path = tasks_root / LOCK_NAME
    path.write_text(json.dumps(compute_lock(tasks_root), indent=2) + "\n", encoding="utf-8")
    return path


def check_lock(tasks_root: Path, allow_missing: str | None = None) -> list[str]:
    """Return a list of differences between the lock file and the files on disk.

    ``allow_missing`` is a path prefix (e.g. "test/") whose locked files may be absent, as in
    CI where the private test split is not checked out. Present files are always verified.
    """
    path = tasks_root / LOCK_NAME
    if not path.exists():
        return [f"{path} missing"]
    locked = json.loads(path.read_text(encoding="utf-8"))
    current = compute_lock(tasks_root)
    problems = [f"{key} changed" for key in ("salt", "dev_fraction") if locked[key] != current[key]]
    lf, cf = locked["files"], current["files"]
    assert isinstance(lf, dict) and isinstance(cf, dict)
    problems += [
        f"{name} removed"
        for name in lf.keys() - cf.keys()
        if not (allow_missing and name.startswith(allow_missing))
    ]
    problems += [f"{name} added" for name in cf.keys() - lf.keys()]
    problems += [f"{name} modified" for name in lf.keys() & cf.keys() if lf[name] != cf[name]]
    return sorted(problems)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.split")
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assign")
    a.add_argument("src", type=Path)
    a.add_argument("tasks_root", type=Path)
    sub.add_parser("lock").add_argument("tasks_root", type=Path)
    check = sub.add_parser("check")
    check.add_argument("tasks_root", type=Path)
    check.add_argument("--allow-missing", help="path prefix that may be absent, e.g. test/")
    args = parser.parse_args(argv)

    if args.cmd == "assign":
        write_split(args.src, args.tasks_root)
    elif args.cmd == "lock":
        print(f"wrote {write_lock(args.tasks_root)}")
    else:
        problems = check_lock(args.tasks_root, args.allow_missing)
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
