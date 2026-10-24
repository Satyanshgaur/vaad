"""Turn difficulty signals used by the routing policy. Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Difficulty:
    n_tools: int
    multi_call: bool
    has_values: bool


def signals(user_turn: str, tools: list[dict[str, Any]]) -> Difficulty:
    """Number of tools offered, multi-call cues, and numbers/dates present in the turn."""
    raise NotImplementedError("Phase 3")
