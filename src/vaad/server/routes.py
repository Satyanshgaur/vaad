"""OpenAI-compatible routes. Implemented in Phase 1 (weeks 2-3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1")


@router.post("/chat/completions")
async def chat_completions(body: dict[str, Any]) -> dict[str, Any]:
    """Pipeline: detect language -> route -> call backend -> validate -> canonicalize -> decide.

    With ``gateway_enabled: false`` this must be a byte-faithful passthrough (gate 7).
    """
    raise HTTPException(status_code=501, detail="not implemented yet (Phase 1)")


@router.get("/models")
async def models() -> dict[str, Any]:
    raise HTTPException(status_code=501, detail="not implemented yet (Phase 1)")
