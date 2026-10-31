"""OpenAI-compatible routes.

With ``gateway_enabled: false`` the request and response bodies pass through as raw bytes
(gate 7). With it on, the request is also traced; the grammar and canonicalizer stages are
added in later weeks and will rewrite the response here.
"""

from __future__ import annotations

import contextlib
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from vaad.server.backend import BackendClient, BackendError, BackendResponse
from vaad.server.pipeline import run_tool_pipeline
from vaad.server.tracing import write_trace
from vaad.types import Tier, Trace

router = APIRouter(prefix="/v1")


def _error(status: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "vaad_error", "code": code}},
        status_code=status,
        headers={"x-request-id": request_id},
    )


def _client(request: Request) -> BackendClient | None:
    client: BackendClient | None = getattr(request.app.state, "small", None)
    return client


def _relay(reply: BackendResponse, request_id: str) -> Response:
    headers = {"x-request-id": request_id}
    if reply.content_type:
        headers["content-type"] = reply.content_type
    return Response(content=reply.body, status_code=reply.status, headers=headers)


def tool_calls_of(reply_body: bytes) -> list[dict[str, Any]]:
    """The tool calls in a chat completion, with arguments decoded when they are valid JSON."""
    try:
        data = json.loads(reply_body)
        messages = [choice["message"] for choice in data["choices"]]
    except (ValueError, KeyError, TypeError):
        return []
    calls = []
    for message in messages:
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            arguments = function.get("arguments")
            # Malformed arguments stay as the raw string: that is exactly what a trace is for.
            with contextlib.suppress(ValueError):
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            calls.append({"name": function.get("name"), "arguments": arguments})
    return calls


@router.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Forward a chat completion to the small backend."""
    request_id = uuid.uuid4().hex
    client = _client(request)
    if client is None:
        return _error(503, "no_backend", "no backend is configured", request_id)
    settings = request.app.state.settings
    raw = await request.body()
    content_type = request.headers.get("content-type")
    authorization = request.headers.get("authorization")
    try:
        payload = json.loads(raw)
    except ValueError:
        return _error(400, "invalid_json", "request body is not valid JSON", request_id)
    if not isinstance(payload, dict):
        return _error(400, "invalid_request", "request body must be a JSON object", request_id)

    if payload.get("stream"):
        if settings.gateway_enabled:
            return _error(
                400, "streaming_unsupported", "stream=true needs gateway_enabled: false", request_id
            )
        try:
            upstream = await client.open_chat_stream(raw, content_type, authorization)
        except BackendError as exc:
            return _error(exc.status, exc.code, exc.message, request_id)
        headers = {"x-request-id": request_id}
        if "content-type" in upstream.headers:
            headers["content-type"] = upstream.headers["content-type"]
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=headers,
            background=BackgroundTask(upstream.aclose),
        )

    start = time.perf_counter()
    trace = Trace(request_id=request_id, tier=Tier.SMALL)
    use_pipeline = (
        settings.gateway_enabled
        and isinstance(payload.get("tools"), list)
        and bool(payload["tools"])
        and payload.get("tool_choice") != "none"
        and isinstance(payload.get("messages"), list)
    )
    try:
        if use_pipeline:
            result = await run_tool_pipeline(
                client,
                payload,
                settings.grammar,
                trace,
                content_type,
                authorization,
                settings.canon,
            )
            reply = BackendResponse(result.status, result.body, result.content_type, 0.0)
        else:
            reply = await client.chat(raw, content_type, authorization)
            trace.stage_ms["backend"] = reply.elapsed_ms
            trace.raw_args = tool_calls_of(reply.body)
    except BackendError as exc:
        if settings.gateway_enabled and settings.trace_path:
            trace.status, trace.error = exc.status, exc.code
            write_trace(trace, settings.trace_path)
        return _error(exc.status, exc.code, exc.message, request_id)

    if settings.gateway_enabled and settings.trace_path:
        trace.status = reply.status
        trace.stage_ms = {k: round(v, 3) for k, v in trace.stage_ms.items()}
        trace.stage_ms["total"] = round((time.perf_counter() - start) * 1000, 3)
        write_trace(trace, settings.trace_path)
    response = _relay(reply, request_id)
    if trace.decision is not None:
        response.headers["x-vaad-decision"] = trace.decision.value
    return response


@router.get("/models")
async def models(request: Request) -> Response:
    request_id = uuid.uuid4().hex
    client = _client(request)
    if client is None:
        return _error(503, "no_backend", "no backend is configured", request_id)
    try:
        reply = await client.models(request.headers.get("authorization"))
    except BackendError as exc:
        return _error(exc.status, exc.code, exc.message, request_id)
    return _relay(reply, request_id)
