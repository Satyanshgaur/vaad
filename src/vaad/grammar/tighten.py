"""Tighten tool schemas so llama-server's JSON-schema grammar constrains more. Phase 1 (week 3)."""

from __future__ import annotations

from typing import Any


def tighten(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``schema`` with patterns, enums and length limits added.

    Dates get an ISO pattern; numbers stay numbers. Never loosens an existing constraint.
    """
    raise NotImplementedError("Phase 1")
