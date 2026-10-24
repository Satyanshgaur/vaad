"""Indian money: "5 lakh", "ढाई करोड़", "Rs 500", "500 rupaye" -> amounts in rupees."""

from __future__ import annotations

from vaad.types import Canonicalized


def parse_amount(text: str) -> Canonicalized | None:
    raise NotImplementedError("Phase 2")
