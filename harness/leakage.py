"""Gate 10: no test-split task text may appear in lexicons, prompts or tests.

Compares word n-grams of every test-split user turn against the text of guarded files.
Exit code 1 lists each overlap.

    python -m harness.leakage
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from harness.schema import load_tasks

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DIR = ROOT / "harness" / "tasks" / "test"
DEFAULT_GUARDED = [
    ROOT / "src" / "vaad" / "canon" / "lexicons",
    ROOT / "harness" / "prompts",
    ROOT / "tests",
    ROOT / "examples",
]
GUARDED_SUFFIXES = {".yaml", ".yml", ".py", ".txt", ".md", ".json", ".jsonl", ".j2"}
DEFAULT_N = 6

# \w alone splits Devanagari words at vowel signs (matras), so include the whole block.
_WORD = re.compile(r"[\w\u0900-\u097F]+")


def ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD.findall(text.casefold())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _guarded_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from (f for f in sorted(p.rglob("*")) if f.suffix in GUARDED_SUFFIXES)


def find_leaks(test_dir: Path, guarded: Iterable[Path], n: int = DEFAULT_N) -> list[str]:
    if not test_dir.exists():
        return []
    test_grams: dict[tuple[str, ...], str] = {}
    for task in load_tasks(test_dir):
        for gram in ngrams(task.user_text(), n):
            test_grams.setdefault(gram, task.id)
    if not test_grams:
        return []
    leaks = []
    for file in _guarded_files(guarded):
        overlap = ngrams(file.read_text(encoding="utf-8", errors="ignore"), n) & test_grams.keys()
        leaks += [f"{file}: '{' '.join(g)}' (task {test_grams[g]})" for g in sorted(overlap)]
    return leaks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.leakage")
    parser.add_argument("--test-dir", type=Path, default=DEFAULT_TEST_DIR)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("guarded", nargs="*", type=Path, default=DEFAULT_GUARDED)
    args = parser.parse_args(argv)
    leaks = find_leaks(args.test_dir, args.guarded, args.n)
    for leak in leaks:
        print(leak, file=sys.stderr)
    print(f"leakage guard: {len(leaks)} overlap(s)")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
