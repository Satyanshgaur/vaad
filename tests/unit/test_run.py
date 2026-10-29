from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from harness.run import Condition, build_request, parse_tool_calls, run_trial, summarize
from harness.schema import ExpectedCall, Message, Task

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ship_order",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string"}, "weight_kg": {"type": "number"}},
                "required": ["date", "weight_kg"],
            },
        },
    }
]

TASK = Task(
    id="vh:ship-1:hinglish",
    source="value_heavy",
    lang="hinglish",
    pair_id="vh:ship-1",
    messages=[Message(role="user", content="parcel kal pahuncha dena, weight do kilo")],
    tools=TOOLS,
    expected_calls=[
        ExpectedCall(name="ship_order", arguments={"date": ["2026-10-25"], "weight_kg": [2]})
    ],
)
COND = Condition(model="m", quant="Q4_K_M", gateway="off", base_url="http://backend")


def response(arguments: Any) -> dict[str, Any]:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    call = {"type": "function", "function": {"name": "ship_order", "arguments": raw}}
    return {"choices": [{"message": {"role": "assistant", "tool_calls": [call]}}]}


@pytest.mark.unit
def test_parse_bad_json() -> None:
    calls, ok = parse_tool_calls(response("{not json"))
    assert not ok and calls[0].arguments == {}


@pytest.mark.unit
def test_parse_no_calls() -> None:
    assert parse_tool_calls({"choices": [{"message": {"content": "?"}}]}) == ([], True)


@pytest.mark.unit
@respx.mock
@pytest.mark.parametrize(
    ("arguments", "correct", "valid", "wrong_value"),
    [
        ({"date": "2026-10-25", "weight_kg": 2}, True, True, False),
        ({"date": "kal", "weight_kg": 2}, False, True, True),  # the motivating failure
        ({"date": "2026-10-25", "weight_kg": "do"}, False, False, False),
    ],
)
def test_run_trial_scoring(
    arguments: dict[str, Any], correct: bool, valid: bool, wrong_value: bool
) -> None:
    respx.post("http://backend/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=response(arguments))
    )
    with httpx.Client() as client:
        result, _ = run_trial(client, TASK, COND, seed=0, temperature=0.7)
    assert (result.correct, result.schema_valid, result.wrong_value) == (
        correct,
        valid,
        wrong_value,
    )


@pytest.mark.unit
@respx.mock
def test_summarize_pass_hat_k() -> None:
    respx.post("http://backend/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=response({"date": "2026-10-25", "weight_kg": 2})),
            httpx.Response(200, json=response({"date": "kal", "weight_kg": 2})),
        ]
    )
    with httpx.Client() as client:
        results = [run_trial(client, TASK, COND, s, 0.7)[0] for s in (0, 1)]
    entry = summarize(results, [TASK], k=2)["m:Q4_K_M:off|hinglish"]
    assert entry["pass@1"][0] == pytest.approx(0.5)
    assert entry["pass^2"][0] == 0.0


@pytest.mark.unit
def test_system_prompt_merges_into_existing_system_message() -> None:
    task = TASK.model_copy(
        update={"messages": [Message(role="system", content="Today is X."), *TASK.messages]}
    )
    cond = Condition(model="m", quant="q", gateway="off", base_url="u", system_prompt="Be ISO.")
    messages = build_request(task, cond, 0, 0.7)["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == "Be ISO.\n\nToday is X."


@pytest.mark.unit
@respx.mock
def test_unparseable_model_output_is_a_failed_trial() -> None:
    message = "The model produced output that does not match the expected peg-native format"
    respx.post("http://backend/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": {"code": 500, "message": message}})
    )
    relevance = TASK.model_copy(update={"expected_calls": [], "category": "irrelevance"})
    with httpx.Client() as client:
        result, _ = run_trial(client, relevance, COND, seed=0, temperature=0.7)
    # Even where calling nothing is right, a malformed call attempt is wrong.
    assert (result.correct, result.schema_valid, result.error) == (False, False, message)


@pytest.mark.unit
@respx.mock
def test_other_server_errors_still_abort() -> None:
    respx.post("http://backend/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": {"message": "CUDA out of memory"}})
    )
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        run_trial(client, TASK, COND, seed=0, temperature=0.7)


@pytest.mark.unit
def test_gateway_flag_is_recorded_and_executes_nothing() -> None:
    flagged = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "kya aap date bata sakte hain?",
                    "vaad_flag": {"reason": "invalid_arguments"},
                }
            }
        ]
    }
    with respx.mock:
        respx.post("http://backend/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=flagged)
        )
        with httpx.Client() as client:
            result, _ = run_trial(client, TASK, COND, seed=0, temperature=0.0)
    assert result.flagged
    assert not result.correct  # a call was expected, so asking back is not a pass
    assert not result.wrong_value
    assert summarize([result], [TASK], k=1)["m:Q4_K_M:off|hinglish"]["flag_rate"][0] == 1.0


@pytest.mark.unit
def test_resume_skips_finished_trials_and_keeps_them(tmp_path: Any) -> None:
    from harness.run import run_grid

    reply = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "ship_order",
                                "arguments": json.dumps({"date": "2026-10-25", "weight_kg": 2}),
                            }
                        }
                    ]
                }
            }
        ]
    }
    with respx.mock:
        route = respx.post("http://backend/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=reply)
        )
        first = run_grid([TASK], [COND], tmp_path, seeds=(0, 1), temperature=0.0)
        assert len(first) == 2 and route.call_count == 2
        # a crash after seed 0 only: drop the last line, then resume
        path = tmp_path / "results.jsonl"
        path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
        resumed = run_grid([TASK], [COND], tmp_path, seeds=(0, 1), temperature=0.0, resume=True)
    assert route.call_count == 3  # only the missing trial ran again
    assert sorted(r.seed for r in resumed) == [0, 1]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
