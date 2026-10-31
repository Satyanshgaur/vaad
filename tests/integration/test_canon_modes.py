"""The four canon modes through the gateway with a mocked backend."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from vaad.config import Backend, CanonSettings, Settings
from vaad.server.app import create_app

BACKEND = "http://backend.test"
URL = f"{BACKEND}/v1/chat/completions"
TOOLS = [{"type": "function", "function": {"name": "ship_order", "parameters": {
    "type": "object",
    "properties": {
        "weight_kg": {"type": "number", "description": "Parcel weight in kilograms"},
        "delivery_date": {"type": "string", "description": "Delivery date, YYYY-MM-DD"},
    },
    "required": ["weight_kg", "delivery_date"],
}}}]  # fmt: skip


NEUTRAL_DATE_TOOLS = [{"type": "function", "function": {"name": "ship_order", "parameters": {
    "type": "object",
    "properties": {
        "weight_kg": {"type": "number", "description": "Parcel weight in kilograms"},
        "date": {"type": "string", "description": "Date, YYYY-MM-DD"},
    },
}}}]  # fmt: skip


def reply(arguments: dict[str, Any]) -> httpx.Response:
    call = {
        "id": "c",
        "type": "function",
        "function": {"name": "ship_order", "arguments": json.dumps(arguments)},
    }
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "tool_calls": [call]}}]}
    )


def client(tmp_path: Path, mode: str) -> TestClient:
    settings = Settings(
        small=Backend(url=BACKEND, model="m"),  # type: ignore[arg-type]
        trace_path=tmp_path / "t.jsonl",
        canon=CanonSettings(mode=mode, ref_date=date(2026, 10, 24)),  # type: ignore[arg-type]
    )
    return TestClient(create_app(settings))


def ask(c: TestClient, text: str, tools: list[dict[str, Any]] | None = None) -> httpx.Response:
    body = {"model": "m", "messages": [{"role": "user", "content": text}], "tools": tools or TOOLS}
    return c.post("/v1/chat/completions", json=body)


def arguments_of(response: httpx.Response) -> dict[str, Any]:
    call = response.json()["choices"][0]["message"]["tool_calls"][0]
    return json.loads(call["function"]["arguments"])  # type: ignore[no-any-return]


@pytest.mark.integration
def test_verify_repairs_a_wrong_value_silently(tmp_path: Path) -> None:
    with respx.mock:
        route = respx.post(URL).mock(
            return_value=reply({"weight_kg": 15, "delivery_date": "2026-10-25"})
        )
        response = ask(client(tmp_path, "verify"), "dedh kilo ka parcel kal tak bhej do")
    assert arguments_of(response) == {"weight_kg": 1.5, "delivery_date": "2026-10-25"}
    assert response.headers["x-vaad-decision"] == "pass"
    assert route.call_count == 1
    trace = json.loads((tmp_path / "t.jsonl").read_text(encoding="utf-8"))
    assert trace["canon_args"][0]["status"] == "repair" and trace["canon_args"][0]["was"] == 15


@pytest.mark.integration
def test_verify_flags_an_ambiguous_date_instead_of_executing(tmp_path: Path) -> None:
    with respx.mock:
        respx.post(URL).mock(return_value=reply({"weight_kg": 2, "date": "2026-10-25"}))
        response = ask(client(tmp_path, "verify"), "2 kilo ka parcel kal", NEUTRAL_DATE_TOOLS)
    assert response.headers["x-vaad-decision"] == "flag"
    flag = response.json()["choices"][0]["message"]["vaad_flag"]
    assert any("date" in e for e in flag["errors"])


@pytest.mark.integration
def test_annotate_changes_only_what_the_model_sees(tmp_path: Path) -> None:
    with respx.mock:
        route = respx.post(URL).mock(
            return_value=reply({"weight_kg": 1.5, "delivery_date": "2026-10-25"})
        )
        response = ask(client(tmp_path, "annotate"), "dedh kilo ka parcel kal tak bhej do")
    sent = json.loads(route.calls.last.request.content)["messages"][-1]["content"]
    assert "dedh [=1.5] kilo" in sent
    assert arguments_of(response)["weight_kg"] == 1.5  # no verification in annotate mode


@pytest.mark.integration
def test_off_leaves_everything_alone(tmp_path: Path) -> None:
    with respx.mock:
        route = respx.post(URL).mock(
            return_value=reply({"weight_kg": 15, "delivery_date": "2026-10-25"})
        )
        response = ask(client(tmp_path, "off"), "dedh kilo ka parcel kal tak bhej do")
    assert arguments_of(response)["weight_kg"] == 15
    assert json.loads(route.calls.last.request.content)["messages"][-1]["content"].startswith(
        "dedh kilo"
    )


@pytest.mark.integration
def test_both_annotates_and_verifies(tmp_path: Path) -> None:
    with respx.mock:
        route = respx.post(URL).mock(
            return_value=reply({"weight_kg": 15, "delivery_date": "2026-10-25"})
        )
        response = ask(client(tmp_path, "both"), "dedh kilo ka parcel kal tak bhej do")
    assert "[=1.5]" in json.loads(route.calls.last.request.content)["messages"][-1]["content"]
    assert arguments_of(response)["weight_kg"] == 1.5
