"""Rule-based routing policy (v1 does no learning). Phase 3."""

from __future__ import annotations

from vaad.config import Routing
from vaad.router.difficulty import Difficulty
from vaad.router.langid import LangResult
from vaad.types import Tier


def route(lang: LangResult, difficulty: Difficulty, cfg: Routing) -> Tier:
    """Hindi/Hinglish plus any difficulty signal -> strong tier; otherwise small."""
    raise NotImplementedError("Phase 3")
