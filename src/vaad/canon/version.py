"""A short fingerprint of the lexicons and rules, written into every audit record.

Two runs with the same fingerprint used the same word lists; a changed fingerprint says the parsers
may read the same text differently.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

from vaad import __version__

_LEXICONS = Path(__file__).parent / "lexicons"


@cache
def canon_version() -> str:
    digest = hashlib.sha256()
    for path in sorted(_LEXICONS.glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return f"{__version__}+lex.{digest.hexdigest()[:10]}"
