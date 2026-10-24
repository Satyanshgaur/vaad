"""Phone numbers and IDs from spoken digits ("double nine"), checked by length."""

from __future__ import annotations

from vaad.types import Canonicalized


def parse_phone(text: str, length: int = 10) -> Canonicalized | None:
    raise NotImplementedError("Phase 2")
