"""Privacy-safe lexicon gap miner.

Finds words that sit right before a time, money, quantity or duration anchor ("baje", "rupaye",
"kilo", "ghante") and are not in any lexicon. Those are the candidate missing number spellings.
The report holds counts of single words only, and only words seen at least ``min_count`` times
(k-anonymity), so a private corpus can be mined and the result shared. No sentence is ever kept.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from vaad.canon.lexicon import number_lexicon
from vaad.canon.lexicon_time import time_date_lexicon
from vaad.canon.tokens import tokenize

_MONEY = frozenset({"rupaye", "rupay", "rupaiye", "rupees", "rs", "rupiya", "रुपये", "रुपए"})
_QUANTITY = frozenset({"kilo", "kg", "litre", "liter", "ltr", "gram", "darjan", "dozen", "packet"})
_DURATION = frozenset({"ghanta", "ghante", "minute", "min", "mins", "din", "hafte"})


def _known() -> frozenset[str]:
    nl, tl = number_lexicon(), time_date_lexicon()
    words: set[str] = set(nl.units) | set(nl.multipliers) | set(nl.fractions) | set(nl.modifiers)
    words |= nl.verb_stems | nl.number_followers | nl.ambiguous
    for name in tl.__slots__:
        value = getattr(tl, name)
        words |= set(value)
    return frozenset(words)


def _anchors() -> dict[str, str]:
    out = {w: "time" for w in time_date_lexicon().baje}
    out.update({w: "money" for w in _MONEY})
    out.update({w: "quantity" for w in _QUANTITY})
    out.update({w: "duration" for w in _DURATION})
    return out


def mine(texts: Iterable[str], min_count: int = 3) -> dict[str, object]:
    """Counts of unknown words before anchors. Only words with count >= ``min_count`` are kept."""
    known, anchors = _known(), _anchors()
    counts: Counter[tuple[str, str]] = Counter()
    total = hits = 0
    for text in texts:
        total += 1
        toks = tokenize(text)
        for i in range(1, len(toks)):
            kind = anchors.get(toks[i].norm)
            prev = toks[i - 1]
            if kind is None or toks[i].kind != "word":
                continue
            hits += 1
            if prev.kind == "word" and prev.norm not in known and len(prev.norm) > 1:
                counts[(kind, prev.norm)] += 1
    rows = [
        {"kind": k, "word": w, "count": c} for (k, w), c in counts.most_common() if c >= min_count
    ]
    return {"texts": total, "anchor_hits": hits, "min_count": min_count, "candidates": rows}


def read_column(path: str | Path, column: str) -> list[str]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return [row[column] for row in csv.DictReader(f) if row.get(column)]
