"""Import paired BFCL-Hi (Hindi) and BFCL (English) live tasks.

BFCL-Hi (nvidia/BFCL-Hi, CC-BY-4.0) translates BFCL v2 live questions; Gorilla's BFCL
(Apache-2.0) has the English originals under the same ids. Function descriptions changed a
little between BFCL v2 and v4, so both languages use BFCL-Hi's functions and ground truth, and
the English question comes from v4. Pairs whose ground truth differs between versions are
dropped, because the English question may no longer match the v2 answer.

    python -m harness.importers.bfcl data/external/bfcl_hi \\
        data/external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data data/raw \\
        --hinglish harness/sources/bfcl_hinglish.yaml
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import yaml

from harness.schema import ExpectedCall, Message, Task

# Planned sample sizes per category (brief: ~150 tasks). BFCL "live_relevance" has no ground
# truth and almost no shared ids, so it is not used; "irrelevance" covers calling nothing.
SAMPLE = {"simple": 60, "multiple": 50, "parallel": 7, "parallel_multiple": 8, "irrelevance": 25}
SEED = 20261024

_TYPE_MAP = {"dict": "object", "float": "number", "tuple": "array", "list": "array"}


def _read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {row["id"]: row for row in rows}


def tool_name(name: str) -> str:
    """OpenAI function names allow [a-zA-Z0-9_-]; BFCL uses dots (uber.ride)."""
    return name.replace(".", "_")


def convert_schema(schema: Any) -> Any:
    """BFCL's Python-flavoured types (dict, float, tuple, any) to JSON Schema."""
    if isinstance(schema, list):
        return [convert_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            if value == "any":
                continue
            out[key] = _TYPE_MAP.get(value, value)
        elif key in ("properties",) and isinstance(value, dict):
            out[key] = {k: convert_schema(v) for k, v in value.items()}
        elif key in ("items", "additionalProperties"):
            out[key] = convert_schema(value)
        else:
            out[key] = value
    return out


def to_tools(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool_name(f["name"]),
                "description": f.get("description", ""),
                "parameters": convert_schema(f.get("parameters", {"type": "object"})),
            },
        }
        for f in functions
    ]


def to_expected(ground_truth: list[dict[str, dict[str, list[Any]]]]) -> list[ExpectedCall]:
    calls = []
    for call in ground_truth:
        ((name, args),) = call.items()
        # BFCL marks "may be omitted" with an empty string among the acceptable values.
        optional = [arg for arg, values in args.items() if "" in values]
        arguments = {arg: [v for v in values if v != ""] for arg, values in args.items()}
        calls.append(ExpectedCall(name=tool_name(name), arguments=arguments, optional=optional))
    return calls


def _first_user_turn(question: list[Any]) -> str:
    # v2 files are a flat message list; v4 nests turns: [[{role, content}, ...]].
    turn = question[0] if question and isinstance(question[0], list) else question
    return next(m["content"] for m in turn if m["role"] == "user")


def build_pairs(hi_dir: Path, en_dir: Path) -> dict[str, list[tuple[Task, Task]]]:
    pairs: dict[str, list[tuple[Task, Task]]] = {}
    for category in SAMPLE:
        hi = _read_jsonl(hi_dir / f"BFCL_v2_live_{category}.json")
        en = _read_jsonl(en_dir / f"BFCL_v4_live_{category}.json")
        if category == "irrelevance":
            hi_gt: dict[str, Any] = {i: {"ground_truth": []} for i in hi}
            en_gt: dict[str, Any] = hi_gt
        else:
            hi_gt = _read_jsonl(hi_dir / "possible_answer" / f"BFCL_v2_live_{category}.json")
            en_gt = _read_jsonl(en_dir / "possible_answer" / f"BFCL_v4_live_{category}.json")
        out = []
        for task_id in sorted(hi.keys() & en.keys() & hi_gt.keys() & en_gt.keys()):
            if hi_gt[task_id]["ground_truth"] != en_gt[task_id]["ground_truth"]:
                continue
            common = {
                "pair_id": f"bfcl:{task_id}",
                "category": category,
                "tools": to_tools(hi[task_id]["function"]),
                "expected_calls": to_expected(hi_gt[task_id]["ground_truth"]),
            }
            out.append(
                (
                    Task(
                        id=f"bfcl_hi:{task_id}",
                        source="bfcl_hi",
                        lang="hi",
                        messages=[
                            Message(role="user", content=_first_user_turn(hi[task_id]["question"]))
                        ],
                        provenance="nvidia/BFCL-Hi (CC-BY-4.0), machine-translated by NVIDIA",
                        **common,
                    ),
                    Task(
                        id=f"bfcl_en:{task_id}",
                        source="bfcl_en",
                        lang="en",
                        messages=[
                            Message(role="user", content=_first_user_turn(en[task_id]["question"]))
                        ],
                        provenance="Gorilla BFCL v4 live (Apache-2.0); functions from BFCL-Hi (v2)",
                        **common,
                    ),
                )
            )
        pairs[category] = out
    return pairs


def sample(pairs: dict[str, list[tuple[Task, Task]]], seed: int = SEED) -> list[tuple[Task, Task]]:
    rng = random.Random(seed)
    chosen = []
    for category, n in SAMPLE.items():
        pool = pairs[category]
        chosen += rng.sample(pool, min(n, len(pool)))
    return chosen


def hinglish_tasks(
    en_tasks: list[Task],
    rewrites: dict[str, str],
    checked_by: list[str] | None = None,
    native_checked: bool = False,
) -> list[Task]:
    """Hinglish versions of the English tasks that have a rewrite, same tools and answers."""
    by_pair = {t.pair_id: t for t in en_tasks}
    missing = rewrites.keys() - by_pair.keys()
    if missing:
        raise ValueError(f"rewrites for tasks not in the sample: {sorted(missing)}")
    return [
        by_pair[pair_id].model_copy(
            update={
                "id": by_pair[pair_id].id.replace("bfcl_en:", "bfcl_hinglish:"),
                "source": "bfcl_hinglish",
                "lang": "hinglish",
                "messages": [Message(role="user", content=text)],
                "provenance": "Hinglish rewrite of BFCL v4 live (Apache-2.0); AI-drafted"
                + ("" if native_checked else ", not yet native-speaker checked"),
                "checked_by": list(checked_by or []),
            }
        )
        for pair_id, text in rewrites.items()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.importers.bfcl")
    parser.add_argument("hi_dir", type=Path)
    parser.add_argument("en_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--hinglish", type=Path, help="YAML of Hinglish rewrites by pair_id")
    args = parser.parse_args(argv)

    chosen = sample(build_pairs(args.hi_dir, args.en_dir))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for index, name in ((0, "bfcl_hi.jsonl"), (1, "bfcl_en.jsonl")):
        path = args.out_dir / name
        path.write_text(
            "".join(pair[index].model_dump_json(exclude_none=True) + "\n" for pair in chosen),
            encoding="utf-8",
        )
        print(f"wrote {len(chosen)} tasks to {path}")
    if args.hinglish:
        source = yaml.safe_load(args.hinglish.read_text(encoding="utf-8"))
        en_tasks = [pair[1] for pair in chosen]
        tasks = hinglish_tasks(
            en_tasks,
            source["tasks"],
            source.get("checked_by"),
            source.get("native_checked", False),
        )
        # Later batches that only an AI pass has seen; never claim a native check for them.
        tasks += hinglish_tasks(
            en_tasks, source.get("tasks_ai_only", {}), source.get("ai_only_checked_by")
        )
        path = args.out_dir / "bfcl_hinglish.jsonl"
        path.write_text(
            "".join(t.model_dump_json(exclude_none=True) + "\n" for t in tasks), encoding="utf-8"
        )
        print(f"wrote {len(tasks)} tasks to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
