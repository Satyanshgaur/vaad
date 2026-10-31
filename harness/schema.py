"""Task and result records. Every task file is JSONL with one ``Task`` per line."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "hi", "hinglish"]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ExpectedCall(BaseModel):
    """One expected call. Each argument maps to the list of acceptable values (BFCL style)."""

    name: str
    arguments: dict[str, list[Any]] = Field(default_factory=dict)
    optional: list[str] = Field(default_factory=list)
    # Free-text arguments (messages, notes): must be a non-empty string, wording not scored.
    free_text: list[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str
    source: Literal["bfcl_hi", "bfcl_en", "bfcl_hinglish", "value_heavy", "human_typed"]
    lang: Lang
    # Same pair_id across a task's English/Hindi/Hinglish versions; splits are made on it.
    pair_id: str
    # "irrelevance": no tool fits, call nothing. "clarify": the turn is ambiguous (e.g. "kal"
    # with no tense cue), so executing any call is wrong; asking back is right.
    category: Literal[
        "simple", "multiple", "parallel", "parallel_multiple", "irrelevance", "clarify"
    ] = "simple"
    messages: list[Message]
    tools: list[dict[str, Any]]
    # Empty for irrelevance and clarify tasks: the correct behaviour is to call nothing.
    expected_calls: list[ExpectedCall]
    # Argument names that carry Indic values (amounts, dates...), for per-field breakdowns.
    value_fields: list[str] = Field(default_factory=list)
    ref_date: date | None = None
    # Where the task came from, and who has checked it (native speakers for rewrites).
    provenance: str = ""
    checked_by: list[str] = Field(default_factory=list)

    def user_text(self) -> str:
        return "\n".join(m.content for m in self.messages if m.role == "user")


class TrialResult(BaseModel):
    task_id: str
    condition: str
    seed: int
    predicted: list[ToolCall]
    correct: bool
    schema_valid: bool
    flagged: bool = False
    # Executed (not flagged) but some value was wrong: the business-critical failure.
    wrong_value: bool = False
    latency_ms: float = 0.0
    # Set when the backend could not parse the model's output into tool calls.
    error: str | None = None


def load_tasks(path: Path) -> list[Task]:
    return list(iter_tasks(path))


def iter_tasks(path: Path) -> Iterator[Task]:
    files = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
    for file in files:
        with file.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield Task.model_validate(json.loads(line))
