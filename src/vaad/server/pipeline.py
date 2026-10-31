"""Tool-call pipeline: tighten the schemas, call the backend, validate, retry once, or flag.

Canonicalization and confidence-based decisions slot in after ``inspect_reply`` in Phase 2.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from vaad.canon import annotate_turn, check_argument
from vaad.canon.version import canon_version
from vaad.config import CanonSettings, GrammarSettings
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


def _mask(value: Any) -> str:
    """Phone numbers go into the audit trail masked to their last two digits."""
    text = str(value)
    return "X" * max(0, len(text) - 2) + text[-2:]


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return str(message["content"])
    return ""


def annotated_messages(messages: list[dict[str, Any]], ref: date) -> list[dict[str, Any]]:
    """A copy of ``messages`` whose last user turn carries the parsed spoken values."""
    out = [dict(m) for m in messages]
    for message in reversed(out):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            message["content"] = annotate_turn(message["content"], ref)
            break
    return out


def canon_pass(
    reply: BackendResponse,
    tools: list[dict[str, Any]],
    turn: str,
    canon: CanonSettings,
    ref: date,
    trace: Trace,
) -> tuple[BackendResponse, list[str], list[str]]:
    """Check each typed argument against the turn: (maybe repaired reply, retry notes, flags)."""
    try:
        data = json.loads(reply.body)
        message = data["choices"][0]["message"]
        calls = message.get("tool_calls") or []
    except (ValueError, KeyError, IndexError, TypeError):
        return reply, [], []
    schemas = {t["function"]["name"]: t["function"].get("parameters", {}).get("properties", {})
               for t in tools}  # fmt: skip
    notes: list[str] = []
    flags: list[str] = []
    changed = False
    for call in calls:
        function = call.get("function", {})
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except ValueError:
            continue
        props = schemas.get(function.get("name"), {})
        for arg, value in list(arguments.items()):
            prop = props.get(arg)
            check = check_argument(arg, prop, value, turn, ref) if isinstance(prop, dict) else None
            if check is None:
                continue
            private = check.kind == "phone"  # phone numbers are masked in the trail
            trace.canon_args.append(
                {
                    "tool": function.get("name"),
                    "arg": arg,
                    "kind": check.kind,
                    "status": check.status,
                    "was": _mask(value) if private else value,
                    "value": _mask(check.value) if private else check.value,
                    "confidence": round(check.confidence, 3),
                    "reason": check.reason,
                    "span": list(check.span) if check.span else None,
                }
            )
            if check.status == "agree":
                continue
            where = f"{function.get('name')}.{arg}"
            if check.status == "repair" and check.confidence >= 0.9:
                arguments[arg] = check.value
                changed = True
            elif check.status == "repair" and check.confidence >= 0.6:
                notes.append(
                    f"{where}: you gave {value!r} but the user's words mean {check.value!r}"
                )
            elif (check.status == "ungrounded" and canon.ungrounded == "flag") or check.status in (
                "ambiguous",
                "repair",
            ):
                flags.append(f"{where}: {check.reason}")
        if changed:
            function["arguments"] = json.dumps(arguments, ensure_ascii=False)
    if changed and not flags and not notes:
        body = json.dumps(data, ensure_ascii=False).encode()
        reply = BackendResponse(reply.status, body, reply.content_type, reply.elapsed_ms)
    return reply, notes, flags


def _passthrough(reply: BackendResponse, decision: Decision | None) -> Result:
    return Result(reply.status, reply.body, reply.content_type, decision)


async def run_tool_pipeline(
    client: BackendClient,
    payload: dict[str, Any],
    grammar: GrammarSettings,
    trace: Trace,
    content_type: str | None,
    authorization: str | None,
    canon: CanonSettings | None = None,
) -> Result:
    """Tighten, call, validate, check values; one guided retry; otherwise flag. Fills ``trace``."""
    canon = canon or CanonSettings()
    if canon.mode != "off":
        trace.canon_version = canon_version()
    tools: list[dict[str, Any]] = payload["tools"]
    send_tools = tightened_tools(tools, grammar) if grammar.enabled else tools
    ref = canon.ref_date or date.today()
    turn = _last_user_text(payload["messages"])
    messages = payload["messages"]
    if canon.mode in ("annotate", "both"):
        messages = annotated_messages(messages, ref)

    async def call(call_messages: list[dict[str, Any]]) -> BackendResponse:
        body = json.dumps({**payload, "messages": call_messages, "tools": send_tools}).encode()
        start = time.perf_counter()
        reply = await client.chat(body, content_type, authorization)
        trace.stage_ms["backend"] = trace.stage_ms.get("backend", 0.0) + (
            (time.perf_counter() - start) * 1000
        )
        return reply

    def verify(reply: BackendResponse) -> tuple[BackendResponse, list[str], list[str]]:
        if canon.mode not in ("verify", "both") or not turn:
            return reply, [], []
        start = time.perf_counter()
        out = canon_pass(reply, tools, turn, canon, ref, trace)
        trace.stage_ms["canon"] = (
            trace.stage_ms.get("canon", 0.0) + (time.perf_counter() - start) * 1000
        )
        return out

    def flagged(inspection: Inspection, attempts: int) -> Result:
        trace.decision = Decision.FLAG
        body = flag_body(payload.get("model"), inspection, attempts, trace.request_id)
        return Result(200, body, "application/json", Decision.FLAG)

    reply = await call(messages)
    start = time.perf_counter()
    inspection = inspect_reply(reply, tools)
    trace.stage_ms["validate"] = (time.perf_counter() - start) * 1000
    if inspection is None:
        return _passthrough(reply, None)
    if not inspection.calls and not inspection.errors:
        return _passthrough(reply, None)  # a plain text answer: no tool call to judge
    trace.raw_args = inspection.calls
    if not inspection.errors:
        reply, notes, flags = verify(reply)
        if flags:
            return flagged(Inspection(inspection.calls, flags), 1)
        if not notes:
            trace.decision = Decision.PASS
            return _passthrough(reply, Decision.PASS)
        inspection = Inspection(inspection.calls, notes)

    attempts = 1
    if grammar.retry:
        trace.retried = True
        attempts = 2
        reply = await call(retry_messages(messages, inspection))
        retried = inspect_reply(reply, tools)
        if retried is not None and not retried.errors:
            reply, notes, flags = verify(reply)
            if not notes and not flags:
                trace.decision = Decision.PASS
                return _passthrough(reply, Decision.PASS)
            retried = Inspection(retried.calls, notes + flags)
        inspection = retried or inspection
    return flagged(inspection, attempts)


def new_request_id() -> str:
    return uuid.uuid4().hex
