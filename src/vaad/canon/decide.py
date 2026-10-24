"""Map canonicalizer confidence to a gateway decision."""

from __future__ import annotations

from vaad.config import Thresholds
from vaad.types import Canonicalized, Decision


def decide(results: list[Canonicalized], thresholds: Thresholds) -> Decision:
    """The weakest argument decides: any low-confidence value flags the whole call."""
    if not results:
        return Decision.PASS
    lowest = min(r.confidence for r in results)
    if lowest >= thresholds.pass_:
        return Decision.PASS
    if lowest >= thresholds.retry:
        return Decision.RETRY
    return Decision.FLAG
