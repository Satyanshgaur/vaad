from __future__ import annotations

from pathlib import Path

import pytest

from harness.leakage import (
    DEFAULT_GUARDED,
    DEFAULT_HASH_FILE,
    DEFAULT_TEST_DIR,
    find_leaks,
    ngrams,
    write_hashes,
)
from harness.schema import Message
from tests.unit.test_split import make_task


def write_test_split(root: Path, text: str) -> Path:
    test_dir = root / "test"
    test_dir.mkdir()
    task = make_task("p1", "hinglish").model_copy(
        update={"messages": [Message(role="user", content=text)]}
    )
    (test_dir / "t.jsonl").write_text(task.model_dump_json() + "\n")
    return test_dir


@pytest.mark.unit
def test_ngrams_unicode() -> None:
    assert ("मेरा", "ऑर्डर") in ngrams("मेरा ऑर्डर कल", 2)


@pytest.mark.unit
def test_detects_planted_overlap(tmp_path: Path) -> None:
    turn = "mera order kal tak bhej do please do kilo wala"
    test_dir = write_test_split(tmp_path, turn)
    lexicon = tmp_path / "lex.yaml"
    lexicon.write_text(f"# copied: {turn.upper()}\n")
    leaks = find_leaks(test_dir, [lexicon], n=6)
    assert leaks and "task p1-hinglish" in leaks[0]


@pytest.mark.unit
def test_clean(tmp_path: Path) -> None:
    test_dir = write_test_split(tmp_path, "mera order kal tak bhej do please do kilo wala")
    other = tmp_path / "other.py"
    other.write_text("an unrelated file about kal and do kilo\n")
    assert find_leaks(test_dir, [other], n=6) == []


@pytest.mark.unit
def test_repo_is_clean() -> None:
    assert find_leaks(DEFAULT_TEST_DIR, DEFAULT_GUARDED, hash_file=DEFAULT_HASH_FILE) == []


@pytest.mark.unit
def test_hash_file_detects_overlap_without_test_text(tmp_path: Path) -> None:
    turn = "mera order kal tak bhej do please do kilo wala"
    test_dir = write_test_split(tmp_path, turn)
    hash_file = tmp_path / "hashes.txt"
    assert write_hashes(test_dir, hash_file) > 0
    assert turn not in hash_file.read_text()

    (test_dir / "t.jsonl").unlink()  # CI: the private test split is not checked out
    lexicon = tmp_path / "lex.yaml"
    lexicon.write_text(f"# copied: {turn}\n")
    leaks = find_leaks(test_dir, [lexicon], hash_file=hash_file)
    assert leaks and "task p1-hinglish" in leaks[0]
