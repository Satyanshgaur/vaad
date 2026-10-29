from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from harness.preprocess import romanize_task, translate_tasks, with_user_text
from harness.romanize import romanize_hindi
from harness.schema import Message, Task


def _task(text: str) -> Task:
    return Task(
        id="bfcl_hi:t",
        source="bfcl_hi",
        lang="hi",
        pair_id="bfcl:t",
        messages=[Message(role="system", content="sys"), Message(role="user", content=text)],
        tools=[],
        expected_calls=[],
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hindi", "roman"),
    [
        ("पार्सल PQ77 आज शाम तक भेज दो", "parsal PQ77 aj sham tak bhej do"),
        ("परसों डिलीवर कर दो", "parson dilivar kar do"),
        ("तापमान ९ डिग्री", "tapman 9 digri"),
    ],
)
def test_romanize_reads_like_typed_hindi(hindi: str, roman: str) -> None:
    assert romanize_hindi(hindi) == roman


@pytest.mark.unit
def test_latin_text_digits_and_names_are_untouched() -> None:
    text = "Book 'Cha Cha Cha' by Käärijä at 9:30, id U123456"
    assert romanize_hindi(text) == text
    assert romanize_hindi("") == ""


@pytest.mark.unit
def test_romanize_task_changes_only_the_user_turn() -> None:
    task = romanize_task(_task("अब सुबह कॉल करो"))
    assert [m.content for m in task.messages] == ["sys", "ab subah kol karo"]
    assert with_user_text(_task("x"), "y").messages[0].content == "sys"


@pytest.mark.unit
def test_translate_first_caches_and_falls_back(tmp_path: Any) -> None:
    tasks = [_task("अब सुबह कॉल करो"), _task("")]
    tasks[1] = tasks[1].model_copy(update={"id": "bfcl_hi:u"})
    replies = iter(["Send it by tomorrow", "   "])
    with respx.mock:
        route = respx.post("http://backend/v1/chat/completions").mock(
            side_effect=lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": next(replies)}}]}
            )
        )
        out = translate_tasks(tasks, "http://backend", "m", {}, tmp_path / "tr.json")
        assert route.call_count == 2
        again = translate_tasks(tasks, "http://backend", "m", {}, tmp_path / "tr.json")
        assert route.call_count == 2  # second pass is served from the cache
    assert out[0].user_text() == "Send it by tomorrow"
    assert out[1].user_text() == ""  # an empty translation keeps the original text
    assert again[0].user_text() == out[0].user_text()
