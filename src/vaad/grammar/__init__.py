"""Schema tightening before generation and validation after it."""

from vaad.grammar.tighten import tighten
from vaad.grammar.validate import validate

__all__ = ["tighten", "validate"]
