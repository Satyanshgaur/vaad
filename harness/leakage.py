"""Gate 10: no test-split task text may appear in lexicons, prompts or tests.

Compares word n-grams of every test-split user turn against the text of guarded files.
Exit code 1 lists each overlap. The test split is private, so CI compares against the
published n-gram hashes in harness/tasks/test_ngrams.txt instead of the text.

    python -m harness.leakage
    python -m harness.leakage --write-hashes   # after the test split changes (maintainers)
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from harness.schema import load_tasks

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DIR = ROOT / "harness" / "tasks" / "test"
DEFAULT_HASH_FILE = ROOT / "harness" / "tasks" / "test_ngrams.txt"
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


def gram_hash(gram: tuple[str, ...]) -> str:
    return hashlib.sha256(" ".join(gram).encode()).hexdigest()[:20]


def test_gram_index(test_dir: Path, n: int = DEFAULT_N) -> dict[str, str]:
    """Hash of every test-split n-gram -> the first task id containing it."""
    index: dict[str, str] = {}
    if test_dir.exists() and any(test_dir.glob("*.jsonl")):
        for task in load_tasks(test_dir):
            for gram in ngrams(task.user_text(), n):
                index.setdefault(gram_hash(gram), task.id)
    return index


def write_hashes(test_dir: Path, out: Path, n: int = DEFAULT_N) -> int:
    index = test_gram_index(test_dir, n)
    lines = [f"# word {n}-gram hashes of the private test split (harness.leakage)"]
    lines += [f"{h} {task_id}" for h, task_id in sorted(index.items())]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(index)


def read_hashes(path: Path) -> dict[str, str]:
    index = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            h, task_id = line.split(" ", 1)
            index[h] = task_id
    return index


def find_leaks(
    test_dir: Path,
    guarded: Iterable[Path],
    n: int = DEFAULT_N,
    hash_file: Path | None = None,
) -> list[str]:
    """Overlaps between guarded files and the test split.

    Uses the test task files when present (maintainers); otherwise the published hash file,
    so CI can run the guard without the private test text.
    """
    index = test_gram_index(test_dir, n)
    if not index and hash_file is not None and hash_file.exists():
        index = read_hashes(hash_file)
    if not index:
        return []
    leaks = []
    for file in _guarded_files(guarded):
        for gram in sorted(ngrams(file.read_text(encoding="utf-8", errors="ignore"), n)):
            task_id = index.get(gram_hash(gram))
            if task_id is not None:
                leaks.append(f"{file}: '{' '.join(gram)}' (task {task_id})")
    return leaks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.leakage")
    parser.add_argument("--test-dir", type=Path, default=DEFAULT_TEST_DIR)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH_FILE)
    parser.add_argument(
        "--write-hashes", action="store_true", help="regenerate the hash file from test tasks"
    )
    parser.add_argument("guarded", nargs="*", type=Path, default=DEFAULT_GUARDED)
    args = parser.parse_args(argv)
    if args.write_hashes:
        count = write_hashes(args.test_dir, args.hash_file, args.n)
        print(f"wrote {count} hashes to {args.hash_file}")
        return 0
    leaks = find_leaks(args.test_dir, args.guarded, args.n, args.hash_file)
    for leak in leaks:
        print(leak, file=sys.stderr)
    print(f"leakage guard: {len(leaks)} overlap(s)")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
