from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.schema import Message, Task
from harness.split import assign, check_lock, split_tasks, write_lock, write_split


def make_task(pair_id: str, lang: str = "en") -> Task:
    return Task.model_validate(
        {
            "id": f"{pair_id}-{lang}",
            "source": "value_heavy",
            "lang": lang,
            "pair_id": pair_id,
            "messages": [{"role": "user", "content": f"task {pair_id}"}],
            "tools": [],
            "expected_calls": [],
        }
    )


@pytest.mark.unit
def test_assign_is_deterministic() -> None:
    assert [assign(f"p{i}") for i in range(50)] == [assign(f"p{i}") for i in range(50)]


@pytest.mark.unit
def test_fraction_close_to_40_percent() -> None:
    dev = sum(assign(f"pair-{i}") == "dev" for i in range(5000))
    assert 0.37 < dev / 5000 < 0.43


@pytest.mark.unit
def test_pairs_stay_together() -> None:
    tasks = [make_task(f"p{i}", lang) for i in range(100) for lang in ("en", "hi", "hinglish")]
    splits = split_tasks(tasks)
    dev_pairs = {t.pair_id for t in splits["dev"]}
    test_pairs = {t.pair_id for t in splits["test"]}
    assert not dev_pairs & test_pairs
    assert len(splits["dev"]) + len(splits["test"]) == 300


@pytest.mark.unit
def test_lock_detects_changes(tmp_path: Path) -> None:
    raw = tmp_path / "raw.jsonl"
    raw.write_text("".join(make_task(f"p{i}").model_dump_json() + "\n" for i in range(20)))
    root = tmp_path / "tasks"
    write_split(raw, root)
    write_lock(root)
    assert check_lock(root) == []

    test_file = root / "test" / "raw.jsonl"
    test_file.write_text(test_file.read_text() + make_task("extra").model_dump_json() + "\n")
    assert check_lock(root) == ["test/raw.jsonl modified"]

    lock = json.loads((root / "SPLITS.lock").read_text())
    assert lock["salt"] == "vaad-split-v1"


@pytest.mark.unit
def test_missing_lock(tmp_path: Path) -> None:
    assert check_lock(tmp_path)[0].endswith("missing")


@pytest.mark.unit
def test_allow_missing_private_split(tmp_path: Path) -> None:
    raw = tmp_path / "raw.jsonl"
    raw.write_text("".join(make_task(f"p{i}").model_dump_json() + "\n" for i in range(20)))
    root = tmp_path / "tasks"
    write_split(raw, root)
    write_lock(root)
    (root / "test" / "raw.jsonl").unlink()
    assert check_lock(root) == ["test/raw.jsonl removed"]
    assert check_lock(root, allow_missing="test/") == []
    (root / "dev" / "raw.jsonl").write_text("")
    assert check_lock(root, allow_missing="test/") == ["dev/raw.jsonl modified"]


@pytest.mark.unit
def test_test_pairs_repeating_dev_text_are_dropped() -> None:
    dev_pair = next(f"p{i}" for i in range(100) if assign(f"p{i}") == "dev")
    test_pair = next(f"p{i}" for i in range(100) if assign(f"p{i}") == "test")
    same = "What's the weather in Boston?"
    tasks = [
        make_task(dev_pair).model_copy(update={"messages": [Message(role="user", content=same)]}),
        make_task(test_pair, "en").model_copy(
            update={"messages": [Message(role="user", content=f"  {same.upper()} ")]}
        ),
        make_task(test_pair, "hi"),
    ]
    splits = split_tasks(tasks)
    assert [t.pair_id for t in splits["dev"]] == [dev_pair]
    assert splits["test"] == []  # whole pair dropped, every language
