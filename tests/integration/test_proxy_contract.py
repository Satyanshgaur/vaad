"""Gate 7: OpenAI response shape, byte-faithful passthrough and error mapping (mocked backend)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from vaad.config import Backend, Settings
from vaad.server.app import create_app

BACKEND = "http://backend.test"
CHAT_URL = f"{BACKEND}/v1/chat/completions"

# Deliberately not what json.dumps would emit: odd spacing, key order, unicode, big floats.
ODD_REPLY = (
    b'{ "id" : "chatcmpl-1","object":"chat.completion",\n  "choices":[{"index":0,'
    b'"finish_reason":"tool_calls","message":{"role":"assistant","content":null,'
    b'"tool_calls":[{"id":"c1","type":"function","function":{"name":"get_weather",'
    b'"arguments":"{\\"city\\":\\"Pune\\",\\"unit\\":\\"celsius\\"}"}}]}}],'
    b'"note":"\xe0\xa4\x95\xe0\xa4\xb2","big":1.0e21 }'
)
REQUEST = {
    "model": "small-q4",
    "messages": [{"role": "user", "content": "Pune ka mausam batao Celsius mein"}],
    "tools": [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
}


def make_client(tmp_path: Path, *, enabled: bool) -> tuple[TestClient, Path]:
    trace = tmp_path / "trace.jsonl"
    settings = Settings(
        gateway_enabled=enabled,
        small=Backend(url=BACKEND, model="small-q4"),  # type: ignore[arg-type]
        trace_path=trace,
    )
    return TestClient(create_app(settings)), trace


@pytest.mark.integration
@pytest.mark.parametrize("enabled", [False, True])
def test_reply_bytes_and_status_are_untouched(tmp_path: Path, enabled: bool) -> None:
    client, _ = make_client(tmp_path, enabled=enabled)
    with respx.mock:
        respx.post(CHAT_URL).mock(
            return_value=httpx.Response(
                200, content=ODD_REPLY, headers={"content-type": "application/json"}
            )
        )
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert response.status_code == 200
    assert response.content == ODD_REPLY
    assert response.headers["content-type"] == "application/json"


@pytest.mark.integration
def test_request_bytes_reach_the_backend_unchanged(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, enabled=False)
    sent = '{"model":"small-q4",  "messages":[{"role":"user","content":"कल"}]}'.encode()
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
        client.post(
            "/v1/chat/completions", content=sent, headers={"content-type": "application/json"}
        )
    assert route.calls.last.request.content == sent


@pytest.mark.integration
@pytest.mark.parametrize("status", [400, 404, 429, 500])
def test_backend_error_replies_pass_through(tmp_path: Path, status: int) -> None:
    client, _ = make_client(tmp_path, enabled=True)
    body = b'{"error":{"message":"nope"}}'
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=httpx.Response(status, content=body))
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert response.status_code == status
    assert response.content == body


@pytest.mark.integration
def test_authorization_is_forwarded_unless_a_key_is_configured(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, enabled=False)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json={}))
        client.post("/v1/chat/completions", json=REQUEST, headers={"authorization": "Bearer mine"})
    assert route.calls.last.request.headers["authorization"] == "Bearer mine"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("raised", "status", "code"),
    [
        (httpx.ConnectError("refused"), 502, "backend_unreachable"),
        (httpx.ReadTimeout("slow"), 504, "backend_timeout"),
    ],
)
def test_unreachable_backend_maps_to_openai_style_error(
    tmp_path: Path, raised: Exception, status: int, code: str
) -> None:
    client, _ = make_client(tmp_path, enabled=True)
    with respx.mock:
        respx.post(CHAT_URL).mock(side_effect=raised)
        response = client.post("/v1/chat/completions", json=REQUEST)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["x-request-id"]


@pytest.mark.integration
def test_bad_request_bodies_are_rejected_before_the_backend(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, enabled=True)
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json={}))
        assert client.post("/v1/chat/completions", content=b"{nope").status_code == 400
        assert client.post("/v1/chat/completions", json=[1, 2]).status_code == 400
    assert not route.called


@pytest.mark.integration
def test_streaming_is_refused_when_the_gateway_is_on(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, enabled=True)
    response = client.post("/v1/chat/completions", json={**REQUEST, "stream": True})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "streaming_unsupported"


@pytest.mark.integration
def test_streaming_passes_through_when_the_gateway_is_off(tmp_path: Path) -> None:
    client, trace = make_client(tmp_path, enabled=False)
    sse = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
    with respx.mock:
        respx.post(CHAT_URL).mock(
            return_value=httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        )
        response = client.post("/v1/chat/completions", json={**REQUEST, "stream": True})
    assert response.content == sse
    assert response.headers["content-type"].startswith("text/event-stream")
    assert not trace.exists()


@pytest.mark.integration
def test_models_endpoint_relays_the_backend_list(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, enabled=True)
    body = b'{"object":"list","data":[{"id":"small-q4","object":"model"}]}'
    with respx.mock:
        respx.get(f"{BACKEND}/v1/models").mock(return_value=httpx.Response(200, content=body))
        response = client.get("/v1/models")
    assert response.status_code == 200
    assert response.content == body


@pytest.mark.integration
def test_no_backend_configured_is_a_503() -> None:
    assert TestClient(create_app()).post("/v1/chat/completions", json=REQUEST).status_code == 503


@pytest.mark.integration
def test_one_trace_line_per_request_when_enabled(tmp_path: Path) -> None:
    client, trace = make_client(tmp_path, enabled=True)
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=httpx.Response(200, content=ODD_REPLY))
        first = client.post("/v1/chat/completions", json=REQUEST)
        client.post("/v1/chat/completions", json=REQUEST)
    lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    record = lines[0]
    assert record["request_id"] == first.headers["x-request-id"]
    assert record["tier"] == "small"
    assert record["status"] == 200
    assert record["raw_args"] == [
        {"name": "get_weather", "arguments": {"city": "Pune", "unit": "celsius"}}
    ]
    assert set(record["stage_ms"]) == {"backend", "validate", "total"}
    assert record["decision"] == "pass"
    assert record["retried"] is False


@pytest.mark.integration
def test_trace_keeps_malformed_arguments_as_the_raw_string(tmp_path: Path) -> None:
    client, trace = make_client(tmp_path, enabled=True)
    reply = {
        "choices": [
            {"message": {"tool_calls": [{"function": {"name": "f", "arguments": "{oops"}}]}}
        ]
    }
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=reply))
        client.post("/v1/chat/completions", json=REQUEST)
    record = json.loads(trace.read_text(encoding="utf-8"))
    assert record["raw_args"] == [{"name": "f", "arguments": "{oops"}]


@pytest.mark.integration
def test_backend_failure_is_traced(tmp_path: Path) -> None:
    client, trace = make_client(tmp_path, enabled=True)
    with respx.mock:
        respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
        client.post("/v1/chat/completions", json=REQUEST)
    record = json.loads(trace.read_text(encoding="utf-8"))
    assert record["status"] == 502
    assert record["error"] == "backend_unreachable"


@pytest.mark.integration
def test_disabled_gateway_writes_no_trace(tmp_path: Path) -> None:
    client, trace = make_client(tmp_path, enabled=False)
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=httpx.Response(200, content=ODD_REPLY))
        client.post("/v1/chat/completions", json=REQUEST)
    assert not trace.exists()
