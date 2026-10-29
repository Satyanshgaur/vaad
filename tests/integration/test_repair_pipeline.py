"""Gate 7, part 2: schema tightening, validation, the guided retry and the flag response."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from vaad.config import Backend, GrammarSettings, Settings
from vaad.grammar.tighten import DATE_PATTERN
from vaad.server.app import create_app

BACKEND = "http://backend.test"
CHAT_URL = f"{BACKEND}/v1/chat/completions"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ship_order",
            "description": "Schedule delivery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "delivery_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "weight_kg": {"type": "number"},
                },
                "required": ["order_id", "delivery_date", "weight_kg"],
            },
        },
    }
]
REQUEST = {
    "model": "small-q4",
    "messages": [{"role": "user", "content": "order OD1 kal bhejo, 2 kilo"}],
    "tools": TOOLS,
}


def reply(arguments: dict[str, Any] | str) -> httpx.Response:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "ship_order", "arguments": raw}}
        ],
    }
    return httpx.Response(200, json={"choices": [{"index": 0, "message": message}]})


GOOD = {"order_id": "OD1", "delivery_date": "2026-10-25", "weight_kg": 2}
BAD = {"order_id": "OD1", "delivery_date": "kal", "weight_kg": "2 kilo"}


def make(tmp_path: Path, *, gateway: bool = True, **grammar: Any) -> tuple[TestClient, Path]:
    trace = tmp_path / "trace.jsonl"
    settings = Settings(
        gateway_enabled=gateway,
        small=Backend(url=BACKEND, model="small-q4"),  # type: ignore[arg-type]
        trace_path=trace,
        grammar=GrammarSettings(**grammar),
    )
    return TestClient(create_app(settings)), trace


def sent_bodies(route: respx.Route) -> list[dict[str, Any]]:
    return [json.loads(call.request.content) for call in route.calls]


@pytest.mark.integration
def test_backend_receives_tightened_schemas_but_client_gets_the_reply(tmp_path: Path) -> None:
    client, _ = make(tmp_path)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(GOOD))
        response = client.post("/v1/chat/completions", json=REQUEST)
    props = sent_bodies(route)[0]["tools"][0]["function"]["parameters"]["properties"]
    assert props["delivery_date"]["pattern"] == DATE_PATTERN
    assert response.headers["x-vaad-decision"] == "pass"
    call = response.json()["choices"][0]["message"]["tool_calls"][0]["function"]
    assert json.loads(call["arguments"]) == GOOD


@pytest.mark.integration
def test_loose_date_grammar_sends_no_date_pattern(tmp_path: Path) -> None:
    client, _ = make(tmp_path, date_grammar="loose")
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(GOOD))
        client.post("/v1/chat/completions", json=REQUEST)
    props = sent_bodies(route)[0]["tools"][0]["function"]["parameters"]["properties"]
    assert "pattern" not in props["delivery_date"]


@pytest.mark.integration
def test_grammar_disabled_sends_the_original_tools(tmp_path: Path) -> None:
    client, _ = make(tmp_path, enabled=False)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(GOOD))
        client.post("/v1/chat/completions", json=REQUEST)
    assert sent_bodies(route)[0]["tools"] == TOOLS


@pytest.mark.integration
def test_invalid_call_is_retried_once_with_the_errors(tmp_path: Path) -> None:
    client, trace = make(tmp_path)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(side_effect=[reply(BAD), reply(GOOD)])
        response = client.post("/v1/chat/completions", json=REQUEST)
    first, second = sent_bodies(route)
    assert len(second["messages"]) == len(first["messages"]) + 1
    note = second["messages"][-1]
    assert note["role"] == "user"
    assert "weight_kg" in note["content"]
    assert "'2 kilo' is not of type 'number'" in note["content"]
    assert response.headers["x-vaad-decision"] == "pass"
    record = json.loads(trace.read_text(encoding="utf-8"))
    assert record["retried"] is True
    assert record["decision"] == "pass"
    assert record["raw_args"][0]["arguments"] == BAD  # the trace keeps the first attempt


@pytest.mark.integration
def test_still_invalid_after_the_retry_returns_a_flag(tmp_path: Path) -> None:
    client, trace = make(tmp_path)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(BAD))
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert len(route.calls) == 2
    assert response.status_code == 200
    assert response.headers["x-vaad-decision"] == "flag"
    choice = response.json()["choices"][0]
    assert "tool_calls" not in choice["message"]
    assert choice["finish_reason"] == "stop"
    flag = choice["message"]["vaad_flag"]
    assert flag["tool"] == "ship_order"
    assert flag["attempts"] == 2
    assert any("weight_kg" in e for e in flag["errors"])
    assert json.loads(trace.read_text(encoding="utf-8"))["decision"] == "flag"


@pytest.mark.integration
def test_retry_off_flags_after_one_call(tmp_path: Path) -> None:
    client, _ = make(tmp_path, retry=False)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(BAD))
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert len(route.calls) == 1
    assert response.json()["choices"][0]["message"]["vaad_flag"]["attempts"] == 1


@pytest.mark.integration
def test_malformed_argument_json_is_caught(tmp_path: Path) -> None:
    client, _ = make(tmp_path)
    with respx.mock:
        respx.post(CHAT_URL).mock(side_effect=[reply("{oops"), reply(GOOD)])
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert response.headers["x-vaad-decision"] == "pass"


@pytest.mark.integration
def test_unparseable_model_output_gets_a_retry(tmp_path: Path) -> None:
    client, _ = make(tmp_path)
    broken = httpx.Response(
        500, json={"error": {"message": "Failed to parse input at pos 12", "code": 500}}
    )
    with respx.mock:
        route = respx.post(CHAT_URL).mock(side_effect=[broken, reply(GOOD)])
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert len(route.calls) == 2
    assert response.headers["x-vaad-decision"] == "pass"


@pytest.mark.integration
def test_unknown_tool_is_invalid(tmp_path: Path) -> None:
    client, _ = make(tmp_path, retry=False)
    message = {"tool_calls": [{"function": {"name": "drop_tables", "arguments": "{}"}}]}
    with respx.mock:
        respx.post(CHAT_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": message}]})
        )
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert response.json()["choices"][0]["message"]["vaad_flag"]["tool"] == "drop_tables"


@pytest.mark.integration
def test_text_answers_and_backend_errors_pass_straight_through(tmp_path: Path) -> None:
    client, _ = make(tmp_path)
    text = {"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]}
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=text))
        first = client.post("/v1/chat/completions", json=REQUEST)
        respx.post(CHAT_URL).mock(return_value=httpx.Response(429, content=b"slow down"))
        second = client.post("/v1/chat/completions", json=REQUEST)
    assert first.json() == text
    assert "x-vaad-decision" not in first.headers
    assert (second.status_code, second.content) == (429, b"slow down")
    assert len(route.calls) == 2  # no retry for either


@pytest.mark.integration
def test_requests_without_tools_are_not_rewritten(tmp_path: Path) -> None:
    client, _ = make(tmp_path)
    plain = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json={"ok": 1}))
        client.post("/v1/chat/completions", json=plain)
    assert sent_bodies(route) == [plain]


@pytest.mark.integration
def test_gateway_off_never_rewrites_tools_or_retries(tmp_path: Path) -> None:
    client, _ = make(tmp_path, gateway=False)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=reply(BAD))
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert len(route.calls) == 1
    assert sent_bodies(route)[0] == REQUEST
    assert "x-vaad-decision" not in response.headers
