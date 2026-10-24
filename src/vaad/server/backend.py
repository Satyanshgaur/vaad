"""Async client for llama-server or any OpenAI-compatible backend."""

from __future__ import annotations

from typing import Any

from vaad.config import Backend


class BackendClient:
    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    async def chat(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST ``body`` to ``{url}/v1/chat/completions`` and return the JSON response."""
        raise NotImplementedError("Phase 1")
