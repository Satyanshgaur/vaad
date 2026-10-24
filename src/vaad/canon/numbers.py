"""Number words: "nau sau", "नौ सौ", "dedh", "dhai", "2.5k" -> 900, 900, 1.5, 2.5, 2500."""

from __future__ import annotations

from vaad.types import Canonicalized


def parse_number(text: str) -> Canonicalized | None:
    """Parse the first number expression in ``text``; None if there is none."""
    raise NotImplementedError("Phase 2")
