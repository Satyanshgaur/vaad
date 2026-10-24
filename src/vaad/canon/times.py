"""Times: "shaam 5 baje", "subah saade nau" -> 17:00, 09:30."""

from __future__ import annotations

from vaad.types import Canonicalized


def parse_time(text: str) -> Canonicalized | None:
    raise NotImplementedError("Phase 2")
