"""Units: "2 kilo", "aadha litre" -> number in the unit the schema expects."""

from __future__ import annotations

from vaad.types import Canonicalized


def parse_quantity(text: str, target_unit: str) -> Canonicalized | None:
    raise NotImplementedError("Phase 2")
