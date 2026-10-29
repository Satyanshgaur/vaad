"""Input transformations for the H6 diagnostics: romanize the user turn, or translate it first."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from harness.romanize import romanize_hindi
from harness.schema import Message, Task

TRANSLATE_SYSTEM = (
    "Translate the user's message into English. Keep numbers, names, URLs, IDs and any quoted "
    "text exactly as written. Output only the translation, nothing else."
)


def with_user_text(task: Task, text: str) -> Task:
    """A copy of ``task`` whose last user message is replaced by ``text``."""
    messages = list(task.messages)
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].role == "user":
            messages[i] = Message(role="user", content=text)
            break
    return task.model_copy(update={"messages": messages})


def romanize_task(task: Task) -> Task:
    return with_user_text(task, romanize_hindi(task.user_text()))


def translate_text(
    client: httpx.Client, base_url: str, model: str, text: str, extra: dict[str, Any]
) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": TRANSLATE_SYSTEM},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 512,
        **extra,
    }
    response = client.post(f"{base_url}/v1/chat/completions", json=body)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"].get("content") or ""
    return content.strip() or text  # an empty translation falls back to the original


def translate_tasks(
    tasks: list[Task], base_url: str, model: str, extra: dict[str, Any], cache: Path
) -> list[Task]:
    """Translate each task's user turn once (temperature 0), cached so resumes are cheap."""
    done: dict[str, str] = json.loads(cache.read_text("utf-8")) if cache.exists() else {}
    with httpx.Client(timeout=300.0) as client:
        for task in tasks:
            if task.id not in done:
                done[task.id] = translate_text(client, base_url, model, task.user_text(), extra)
                cache.write_text(json.dumps(done, ensure_ascii=False, indent=1), "utf-8")
    return [with_user_text(t, done[t.id]) for t in tasks]
