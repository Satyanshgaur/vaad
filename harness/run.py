"""Run a task set over a grid of conditions and seeds.

Conditions are model x quant x gateway on/off (x system prompt) x seed; language comes from
the tasks. Output goes to harness/reports/<run>/: results.jsonl (one TrialResult per line),
summary.json, and traces/ with raw backend responses.

    python -m harness.run --tasks harness/tasks/dev --base-url http://127.0.0.1:8080 \\
        --model qwen3.5-4b --quant Q4_K_M --seeds 0 1 2 3 --out harness/reports/baseline-raw
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from harness.metrics import bootstrap_ci, per_task_scores, percentile
from harness.schema import Task, ToolCall, TrialResult, load_tasks
from harness.score import calls_match

SEEDS = (0, 1, 2, 3)
TEMPERATURE = 0.7
MAX_TOKENS = 512


@dataclass(frozen=True)
class Condition:
    model: str
    quant: str
    gateway: str  # "off", "on", or an ablation: "grammar", "canon", "router"
    base_url: str
    system_prompt: str | None = None  # set for the strong-prompt baseline
    # Extra request fields, e.g. {"chat_template_kwargs": {"enable_thinking": false}}.
    extra: dict[str, Any] = field(default_factory=dict, hash=False)

    @property
    def name(self) -> str:
        suffix = "+prompt" if self.system_prompt else ""
        return f"{self.model}:{self.quant}:{self.gateway}{suffix}"


def build_request(
    task: Task, condition: Condition, seed: int, temperature: float
) -> dict[str, Any]:
    messages = [m.model_dump() for m in task.messages]
    if condition.system_prompt:
        # Merge into an existing system message: some chat templates reject two of them.
        if messages and messages[0]["role"] == "system":
            messages[0] = {
                "role": "system",
                "content": f"{condition.system_prompt.strip()}\n\n{messages[0]['content']}",
            }
        else:
            messages.insert(0, {"role": "system", "content": condition.system_prompt})
    return {
        "model": condition.model,
        "messages": messages,
        "tools": task.tools,
        "temperature": temperature,
        "seed": seed,
        "max_tokens": MAX_TOKENS,
        **condition.extra,
    }


def parse_tool_calls(response: dict[str, Any]) -> tuple[list[ToolCall], bool]:
    """Return the predicted calls and whether every call's arguments were valid JSON."""
    message = response["choices"][0]["message"]
    calls, parsed_ok = [], True
    for call in message.get("tool_calls") or []:
        fn = call["function"]
        raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            parsed_ok, args = False, {}
        calls.append(ToolCall(name=fn["name"], arguments=args if isinstance(args, dict) else {}))
    return calls, parsed_ok


def schema_valid(calls: list[ToolCall], task: Task) -> bool:
    """Every call names an offered tool and its arguments satisfy that tool's schema."""
    schemas = {t["function"]["name"]: t["function"].get("parameters", {}) for t in task.tools}
    for call in calls:
        if call.name not in schemas:
            return False
        try:
            if any(Draft202012Validator(schemas[call.name]).iter_errors(call.arguments)):
                return False
        except SchemaError:
            continue  # some BFCL schemas are not valid JSON Schema; don't count against the model
    return True


def score_trial(
    task: Task, condition: Condition, seed: int, calls: list[ToolCall], parsed_ok: bool, ms: float
) -> TrialResult:
    correct = calls_match(calls, task.expected_calls)
    valid = parsed_ok and schema_valid(calls, task)
    # Wrong-value execution: the right functions were called with schema-valid arguments, so a
    # downstream system would execute them, but some value is wrong.
    names_match = sorted(c.name for c in calls) == sorted(e.name for e in task.expected_calls)
    wrong_value = bool(calls) and valid and names_match and not correct
    return TrialResult(
        task_id=task.id,
        condition=condition.name,
        seed=seed,
        predicted=calls,
        correct=correct,
        schema_valid=valid,
        wrong_value=wrong_value,
        latency_ms=ms,
    )


def run_trial(
    client: httpx.Client, task: Task, condition: Condition, seed: int, temperature: float
) -> tuple[TrialResult, dict[str, Any]]:
    body = build_request(task, condition, seed, temperature)
    start = time.perf_counter()
    response = client.post(f"{condition.base_url}/v1/chat/completions", json=body)
    ms = (time.perf_counter() - start) * 1000
    if is_unparseable_output(response):
        # The model emitted malformed tool-call text: a model failure, scored as a wrong,
        # schema-invalid trial rather than aborting the run.
        data = response.json()
        result = score_trial(task, condition, seed, [], False, ms)
        result = result.model_copy(update={"correct": False, "error": data["error"]["message"]})
        return result, data
    response.raise_for_status()
    data = response.json()
    calls, parsed_ok = parse_tool_calls(data)
    return score_trial(task, condition, seed, calls, parsed_ok, ms), data


def is_unparseable_output(response: httpx.Response) -> bool:
    """llama-server answers 500 when it cannot parse the model's tool-call output."""
    if response.status_code != 500:
        return False
    try:
        message = str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return False
    return "does not match the expected" in message or "Failed to parse" in message


def run_grid(
    tasks: list[Task],
    conditions: list[Condition],
    out_dir: Path,
    seeds: tuple[int, ...] = SEEDS,
    temperature: float = TEMPERATURE,
    timeout_s: float = 300.0,
) -> list[TrialResult]:
    (out_dir / "traces").mkdir(parents=True, exist_ok=True)
    results: list[TrialResult] = []
    with (
        httpx.Client(timeout=timeout_s) as client,
        (out_dir / "results.jsonl").open("w", encoding="utf-8") as results_file,
        (out_dir / "traces" / "responses.jsonl").open("w", encoding="utf-8") as traces_file,
    ):
        for cond in conditions:
            for i, task in enumerate(tasks):
                for seed in seeds:
                    result, raw = run_trial(client, task, cond, seed, temperature)
                    results.append(result)
                    results_file.write(result.model_dump_json() + "\n")
                    trace = {"task_id": task.id, "condition": cond.name, "seed": seed, "raw": raw}
                    traces_file.write(json.dumps(trace, ensure_ascii=False) + "\n")
                results_file.flush()
                print(f"[{cond.name}] {i + 1}/{len(tasks)} {task.id}", flush=True)
    return results


def summarize(results: list[TrialResult], tasks: list[Task], k: int) -> dict[str, Any]:
    """Per condition and language: pass@1, pass^k, schema-valid, wrong-value, latency."""
    lang = {t.id: t.lang for t in tasks}
    groups: dict[tuple[str, str], dict[str, list[TrialResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        groups[(r.condition, lang[r.task_id])][r.task_id].append(r)

    summary: dict[str, Any] = {}
    for (condition, language), by_task in sorted(groups.items()):
        trials = [[r.correct for r in rs] for rs in by_task.values()]
        flat = [r for rs in by_task.values() for r in rs]
        n = min(len(t) for t in trials)
        entry: dict[str, Any] = {
            "tasks": len(trials),
            "trials_per_task": n,
            "pass@1": bootstrap_ci(per_task_scores(trials, 1, "pass@k")),
            "schema_valid": bootstrap_ci([float(r.schema_valid) for r in flat]),
            "wrong_value": bootstrap_ci([float(r.wrong_value) for r in flat]),
            "latency_ms_p50": percentile([r.latency_ms for r in flat], 50),
            "latency_ms_p95": percentile([r.latency_ms for r in flat], 95),
        }
        if n >= k:
            entry[f"pass^{k}"] = bootstrap_ci(per_task_scores(trials, k))
        summary[f"{condition}|{language}"] = entry
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.run")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--quant", required=True)
    parser.add_argument("--gateway", default="off")
    parser.add_argument("--system-prompt", type=Path)
    parser.add_argument("--no-think", action="store_true", help="disable thinking (Qwen3.x)")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--limit", type=int, help="first N tasks only (timing, smoke)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    tasks = load_tasks(args.tasks)[: args.limit]
    condition = Condition(
        model=args.model,
        quant=args.quant,
        gateway=args.gateway,
        base_url=args.base_url.rstrip("/"),
        system_prompt=args.system_prompt.read_text(encoding="utf-8")
        if args.system_prompt
        else None,
        extra={"chat_template_kwargs": {"enable_thinking": False}} if args.no_think else {},
    )
    results = run_grid(tasks, [condition], args.out, tuple(args.seeds), args.temperature)
    summary = summarize(results, tasks, k=len(args.seeds))
    meta = {"temperature": args.temperature, "seeds": args.seeds, "tasks": str(args.tasks)}
    (args.out / "summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
