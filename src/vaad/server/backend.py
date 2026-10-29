"""Async client for llama-server or any OpenAI-compatible backend."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from vaad.config import Backend


class BackendError(Exception):
    """The backend could not be reached or did not answer in time (not an HTTP error reply)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class BackendResponse:
    """A backend reply, kept as raw bytes so passthrough can return it untouched."""

    status: int
    body: bytes
    content_type: str | None
    elapsed_ms: float


class BackendClient:
    def __init__(self, backend: Backend, client: httpx.AsyncClient | None = None) -> None:
        self.backend = backend
        self._base = str(backend.url).rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=backend.timeout_s)

    def _headers(self, content_type: str | None, authorization: str | None) -> dict[str, str]:
        headers = {}
        if content_type:
            headers["content-type"] = content_type
        # A configured key wins; otherwise the caller's own credentials go through.
        if self.backend.api_key:
            headers["authorization"] = f"Bearer {self.backend.api_key}"
        elif authorization:
            headers["authorization"] = authorization
        return headers

    async def chat(
        self, body: bytes, content_type: str | None = None, authorization: str | None = None
    ) -> BackendResponse:
        """POST ``body`` unchanged to ``{url}/v1/chat/completions``."""
        return await self._send(
            "POST", "/v1/chat/completions", body, self._headers(content_type, authorization)
        )

    async def models(self, authorization: str | None = None) -> BackendResponse:
        return await self._send("GET", "/v1/models", None, self._headers(None, authorization))

    async def open_chat_stream(
        self, body: bytes, content_type: str | None = None, authorization: str | None = None
    ) -> httpx.Response:
        """Open a streaming chat request. The caller must close the response."""
        request = self._client.build_request(
            "POST",
            f"{self._base}/v1/chat/completions",
            content=body,
            headers=self._headers(content_type, authorization),
        )
        try:
            return await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise _map_error(exc) from exc

    async def _send(
        self, method: str, path: str, body: bytes | None, headers: dict[str, str]
    ) -> BackendResponse:
        start = time.perf_counter()
        try:
            response = await self._client.request(
                method, f"{self._base}{path}", content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise _map_error(exc) from exc
        return BackendResponse(
            status=response.status_code,
            body=response.content,
            content_type=response.headers.get("content-type"),
            elapsed_ms=(time.perf_counter() - start) * 1000,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _map_error(exc: httpx.HTTPError) -> BackendError:
    if isinstance(exc, httpx.TimeoutException):
        return BackendError(504, "backend_timeout", "the backend did not answer in time")
    return BackendError(502, "backend_unreachable", f"could not reach the backend: {exc}")
