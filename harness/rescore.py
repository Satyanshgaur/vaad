"""Field-aware rescoring of stored results (rules fixed in docs/PREREG.md, H2).

The BFCL answer key keeps free-text content in English even when the user asked in Hindi, so a
model that keeps a Hindi todo title in Hindi is scored wrong. This module re-scores stored
predictions, without re-running any model, with three kinds of argument field:

- identifier / format (enums, ids, urls, slugs, dates, times, numbers, commands): exact, as before;
- name (people, places, artists): exact, or equal after transliteration to Latin script;
- free text (titles, content, queries): exact, or semantically equivalent (embedding cosine at
  least tau and every digit sequence of the expected text present in the prediction).

Unplaceable fields are identifiers, so rescoring can only loosen scoring where a field is clearly
a name or free text. It is applied identically to every language and model.

    python -m harness.rescore --results harness/reports/<run>/results.jsonl \\
        --embed-url http://127.0.0.1:8200 --tau 0.80
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

import httpx
from indic_transliteration import sanscript

from harness.schema import Task, ToolCall, load_tasks
from harness.score import ValueMatcher, calls_match, values_equal

FieldClass = Literal["identifier", "name", "free_text"]
Similarity = Callable[[str, str], float]

NAME_SIMILARITY = 0.80
DEFAULT_TAU = 0.80

# Evidence that a field must be exact whatever its name says.
_STRONG_IDENTIFIER = re.compile(
    r"YYYY|HH:MM|dd/mm|\bUUID\b|\bURL\b|URL-friendly|\bslug\b|\bidentifier\b|\bAPI key\b"
    r"|\btoken\b|\bcommand\b|formatted as '|\btrack:",
    re.IGNORECASE,
)
_NAME_FIELDS = frozenset(
    {
        "city", "location", "loc", "area", "district_name", "sub_district_name", "artist",
        "album", "starring", "cast", "directed_by", "name", "artist_name", "partner_name",
        "user_name", "destination", "from_city", "to_city", "departure_location",
        "arrival_location", "origin", "director", "performer",
    }
)  # fmt: skip
_FREE_TEXT_FIELD = re.compile(
    r"(^|_)(content|title|text|message|prompt|keyword|query|label|note|comment|subject|body"
    r"|summary|question|description|metatitle|metadescription)($|_)",
    re.IGNORECASE,
)
_FREE_TEXT_EXTRA = frozenset({"new_alarm_name"})
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DIGITS = re.compile(r"\d+")


def classify_field(name: str, prop: dict[str, Any]) -> FieldClass:
    """The scoring class of one argument field, from its schema alone."""
    if "items" in prop and isinstance(prop["items"], dict):
        prop = prop["items"]
    if prop.get("type") != "string" or "enum" in prop:
        return "identifier"
    description = str(prop.get("description", ""))
    if _STRONG_IDENTIFIER.search(description):
        return "identifier"
    if name.lower() in _NAME_FIELDS:
        return "name"
    if name.lower() in _FREE_TEXT_EXTRA or _FREE_TEXT_FIELD.search(name):
        return "free_text"
    return "identifier"


def field_classes(task: Task) -> dict[str, FieldClass]:
    """Argument name to class for the offered tools; a name classed differently by two tools
    is treated as an identifier."""
    out: dict[str, FieldClass] = {}
    for tool in task.tools:
        props = tool["function"].get("parameters", {}).get("properties", {})
        for arg, prop in props.items():
            cls = classify_field(arg, prop if isinstance(prop, dict) else {})
            out[arg] = cls if out.get(arg, cls) == cls else "identifier"
    return out


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.digit(c, c)) if c.isdigit() else c for c in text)


def digits_preserved(predicted: str, expected: str) -> bool:
    got = set(_DIGITS.findall(_ascii_digits(predicted)))
    return all(d in got for d in _DIGITS.findall(_ascii_digits(expected)))


_DIGRAPHS = (("sh", "s"), ("ch", "c"), ("th", "t"), ("dh", "d"), ("kh", "k"), ("gh", "g"),
             ("ph", "f"), ("bh", "b"), ("ck", "k"), ("q", "k"), ("w", "v"), ("x", "ks"),
             ("z", "j"))  # fmt: skip


def phonetic_key(text: str) -> str:
    """A rough consonant skeleton, comparable across scripts (Devanagari goes via ITRANS)."""
    if _DEVANAGARI.search(text):
        text = sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    for a, b in _DIGRAPHS:
        text = text.replace(a, b)
    skeleton = re.sub(r"(?<=.)[aeiouy]", "", text)  # keep a leading vowel only
    return re.sub(r"(.)\1+", r"\1", skeleton.replace(" ", ""))


def names_equal(predicted: str, expected: str) -> bool:
    if predicted.strip().casefold() == expected.strip().casefold():
        return True
    a, b = phonetic_key(predicted), phonetic_key(expected)
    return bool(a and b) and SequenceMatcher(None, a, b).ratio() >= NAME_SIMILARITY


def make_matcher(task: Task, similarity: Similarity, tau: float = DEFAULT_TAU) -> ValueMatcher:
    classes = field_classes(task)

    def match(arg: str, predicted: Any, expected: Any) -> bool:
        if values_equal(predicted, expected):
            return True
        if isinstance(predicted, list) and isinstance(expected, list):
            return len(predicted) == len(expected) and all(
                match(arg, p, e) for p, e in zip(predicted, expected, strict=True)
            )
        if not (isinstance(predicted, str) and isinstance(expected, str)):
            return False
        cls = classes.get(arg, "identifier")
        if cls == "name":
            return names_equal(predicted, expected)
        if cls == "free_text":
            return digits_preserved(predicted, expected) and similarity(predicted, expected) >= tau
        return False

    return match


class Embedder:
    """Cosine similarity from a llama-server started with ``--embedding`` (bge-m3)."""

    def __init__(self, base_url: str, cache_path: Path | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_path = cache_path
        self._cache: dict[str, list[float]] = {}
        if cache_path and cache_path.exists():
            self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self._client = httpx.Client(timeout=120.0)

    def vector(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key not in self._cache:
            response = self._client.post(f"{self.base_url}/v1/embeddings", json={"input": text})
            response.raise_for_status()
            vec: list[float] = response.json()["data"][0]["embedding"]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            self._cache[key] = [x / norm for x in vec]
        return self._cache[key]

    def similarity(self, a: str, b: str) -> float:
        return sum(x * y for x, y in zip(self.vector(a), self.vector(b), strict=True))

    def save(self) -> None:
        if self.cache_path:
            self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")


def rescore_file(
    results: Path, tasks: dict[str, Task], similarity: Similarity, tau: float, out: Path
) -> tuple[int, int]:
    """Write ``results`` with an added ``correct_fieldaware``; returns (trials, changed)."""
    n = changed = 0
    lines = []
    for line in results.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        task = tasks[row["task_id"]]
        calls = [ToolCall(**c) for c in row["predicted"]]
        row["correct_fieldaware"] = calls_match(
            calls, task.expected_calls, make_matcher(task, similarity, tau)
        )
        n += 1
        changed += row["correct_fieldaware"] != row["correct"]
        lines.append(json.dumps(row, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return n, changed


def dump_classes(tasks: dict[str, Task], out: Path) -> int:
    """List every expected-argument field classed as name or free text, for human review."""
    found: dict[str, str] = {}
    for task in tasks.values():
        classes = field_classes(task)
        for call in task.expected_calls:
            for arg in call.arguments:
                if classes.get(arg, "identifier") != "identifier":
                    found[f"{call.name}.{arg}"] = classes[arg]
    lines = ["# Fields scored as name or free text. Move a field to identifier to make it exact."]
    lines += [f"{key}: {found[key]}" for key in sorted(found)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.rescore")
    parser.add_argument("--results", type=Path, nargs="*", default=[])
    parser.add_argument("--dump-classes", type=Path)
    parser.add_argument("--tasks", type=Path, default=Path("harness/tasks/dev"))
    parser.add_argument("--embed-url")
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU)
    parser.add_argument("--cache", type=Path, default=Path("harness/reports/embed_cache.json"))
    args = parser.parse_args(argv)

    tasks = {t.id: t for t in load_tasks(args.tasks)}
    if args.dump_classes:
        print(f"{dump_classes(tasks, args.dump_classes)} fields -> {args.dump_classes}")
    if not args.results:
        return 0
    if not args.embed_url:
        parser.error("--embed-url is required with --results")
    embedder = Embedder(args.embed_url, args.cache)
    for path in args.results:
        out = path.with_name("results_fieldaware.jsonl")
        n, changed = rescore_file(path, tasks, embedder.similarity, args.tau, out)
        print(f"{path.parent.name}: {n} trials, {changed} changed (tau {args.tau}) -> {out}")
        embedder.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
