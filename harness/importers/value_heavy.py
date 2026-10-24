"""Build the value-heavy task set from harness/sources/value_heavy.yaml.

python -m harness.importers.value_heavy harness/sources/value_heavy.yaml data/raw
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from harness.schema import ExpectedCall, Message, Task

LANGS = ("en", "hi", "hinglish")
PROVENANCE = "vaad value-heavy set; AI-drafted 2026-10-24, not yet native-speaker checked"


def _tool(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, **spec}}


def build(source: dict[str, Any]) -> list[Task]:
    tools = source["tools"]
    tasks = []
    for sc in source["scenarios"]:
        expected = [ExpectedCall.model_validate(e) for e in sc["expected"]]
        value_fields = sorted({arg for e in expected for arg in e.arguments})
        for lang in LANGS:
            tasks.append(
                Task(
                    id=f"vh:{sc['id']}:{lang}",
                    source="value_heavy",
                    lang=lang,
                    pair_id=f"vh:{sc['id']}",
                    category=sc.get("category", "simple"),
                    messages=[
                        Message(role="system", content=source["system"]),
                        Message(role="user", content=sc[lang]),
                    ],
                    tools=[_tool(name, tools[name]) for name in sc["tools"]],
                    expected_calls=expected,
                    value_fields=value_fields,
                    ref_date=source["ref_date"],
                    provenance=PROVENANCE,
                )
            )
    return tasks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.importers.value_heavy")
    parser.add_argument("source", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    tasks = build(yaml.safe_load(args.source.read_text(encoding="utf-8")))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "value_heavy.jsonl"
    out.write_text("".join(t.model_dump_json(exclude_none=True) + "\n" for t in tasks), "utf-8")
    print(f"wrote {len(tasks)} tasks to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
