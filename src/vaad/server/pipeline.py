"""Tool-call pipeline: tighten the schemas, call the backend, validate, retry once, or flag.

Canonicalization and confidence-based decisions slot in after ``inspect_reply`` in Phase 2.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from vaad.config import GrammarSettings
from vaad.grammar.tighten import TightenOptions, tighten
from vaad.grammar.validate import validate_call
from vaad.server.backend import BackendClient, BackendResponse
from vaad.types import Decision, Trace


@dataclass(slots=True)
class Inspection:
    """What came back: the calls the model made and what is wrong with them."""

    calls: list[dict[str, Any]]
    errors: list[str]


@dataclass(slots=True)
class Result:
    status: int
    body: bytes
    content_type: str | None
    decision: Decision | None


def tightened_tools(tools: list[dict[str, Any]], grammar: GrammarSettings) -> list[dict[str, Any]]:
    """Copies of ``tools`` whose parameter schemas are tightened for the backend's grammar."""
    options = TightenOptions(grammar.date_grammar, grammar.infer_enums, grammar.max_length)
    out = []
    for tool in tools:
        function = dict(tool.get("function", {}))
        if isinstance(function.get("parameters"), dict):
            function["parameters"] = tighten(function["parameters"], options)
        out.append({**tool, "function": function})
    return out


def inspect_reply(reply: BackendResponse, tools: list[dict[str, Any]]) -> Inspection | None:
    """Validate the tool calls in ``reply``; None means it is not ours to judge (pass it on)."""
    if reply.status == 500 and _unparseable(reply.body):
        return Inspection([], ["the output was not a valid tool call (could not be parsed)"])
    if reply.status != 200:
        return None
    try:
        message = json.loads(reply.body)["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    calls, errors = [], []
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        name, raw = function.get("name"), function.get("arguments")
        try:
            arguments = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            calls.append({"name": name, "arguments": raw})
            errors.append(f"{name}: arguments are not valid JSON")
            continue
        calls.append({"name": name, "arguments": arguments})
        errors += [f"{name}: {e}" for e in validate_call(str(name), arguments, tools)]
    return Inspection(calls, errors)


def _unparseable(body: bytes) -> bool:
    try:
        message = str(json.loads(body)["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return False
    return "does not match the expected" in message or "Failed to parse" in message


def retry_messages(messages: list[dict[str, Any]], inspection: Inspection) -> list[dict[str, Any]]:
    """The conversation plus one note naming what was wrong, as a user turn so every chat
    template accepts it."""
    problems = "\n".join(f"- {e}" for e in inspection.errors)
    attempted = json.dumps(inspection.calls, ensure_ascii=False) if inspection.calls else "(none)"
    note = (
        "Your previous tool call was rejected.\n"
        f"Call: {attempted}\nProblems:\n{problems}\n"
        "Call the tool again with arguments that fix these problems. Keep names and quoted "
        "text exactly as the user wrote them, and do not guess values the user did not give."
    )
    return [*messages, {"role": "user", "content": note}]


def flag_body(model: Any, inspection: Inspection, attempts: int, request_id: str) -> bytes:
    """An assistant message that asks back instead of executing a doubtful call."""
    tool = next((c["name"] for c in inspection.calls if c.get("name")), None)
    text = (
        "I could not get a valid call for this request"
        + (f" ({tool})" if tool else "")
        + ". Could you rephrase it or give the exact values? Problems: "
        + "; ".join(inspection.errors)
    )
    body = {
        "id": f"chatcmpl-vaad-{request_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": text,
                    "vaad_flag": {
                        "reason": "invalid_arguments",
                        "tool": tool,
                        "errors": inspection.errors,
                        "attempts": attempts,
                    },
                },
            }
        ],
    }
    return json.dumps(body, ensure_ascii=False).encode()


def _passthrough(reply: BackendResponse, decision: Decision | None) -> Result:
    return Result(reply.status, reply.body, reply.content_type, decision)


async def run_tool_pipeline(
    client: BackendClient,
    payload: dict[str, Any],
    grammar: GrammarSettings,
    trace: Trace,
    content_type: str | None,
    authorization: str | None,
) -> Result:
    """Tighten, call, validate; one guided retry; otherwise flag. Fills in ``trace``."""
    tools: list[dict[str, Any]] = payload["tools"]
    send_tools = tightened_tools(tools, grammar) if grammar.enabled else tools

    async def call(messages: list[dict[str, Any]]) -> BackendResponse:
        body = json.dumps({**payload, "messages": messages, "tools": send_tools}).encode()
        start = time.perf_counter()
        reply = await client.chat(body, content_type, authorization)
        trace.stage_ms["backend"] = trace.stage_ms.get("backend", 0.0) + (
            (time.perf_counter() - start) * 1000
        )
        return reply

    reply = await call(payload["messages"])
    start = time.perf_counter()
    inspection = inspect_reply(reply, tools)
    trace.stage_ms["validate"] = (time.perf_counter() - start) * 1000
    if inspection is None:
        return _passthrough(reply, None)
    if not inspection.calls and not inspection.errors:
        return _passthrough(reply, None)  # a plain text answer: no tool call to judge
    trace.raw_args = inspection.calls
    if not inspection.errors:
        trace.decision = Decision.PASS
        return _passthrough(reply, Decision.PASS)

    attempts = 1
    if grammar.retry:
        trace.retried = True
        attempts = 2
        reply = await call(retry_messages(payload["messages"], inspection))
        retried = inspect_reply(reply, tools)
        if retried is not None and not retried.errors:
            trace.decision = Decision.PASS
            return _passthrough(reply, Decision.PASS)
        inspection = retried or inspection
    trace.decision = Decision.FLAG
    body = flag_body(payload.get("model"), inspection, attempts, trace.request_id)
    return Result(200, body, "application/json", Decision.FLAG)


def new_request_id() -> str:
    return uuid.uuid4().hex
