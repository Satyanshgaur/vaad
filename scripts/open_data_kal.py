"""Free gold for the "kal" resolver: Hindi MASSIVE utterances with an English parallel.

"कल" is tomorrow or yesterday. MASSIVE (Amazon, CC BY 4.0) has the same utterance in English, so
the English text says which one the Hindi speaker meant. Prints the counts and a few examples.

    uv run python scripts/open_data_kal.py       # needs scripts/fetch_open_data.sh first
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(os.environ.get("OPEN_DATA", Path.home() / "opendata"))


def load(locale: str) -> dict[str, dict[str, str]]:
    path = glob.glob(str(ROOT / f"massive/*/data/{locale}.jsonl"))[0]
    rows = (json.loads(line) for line in Path(path).read_text("utf-8").splitlines())
    return {r["id"]: r for r in rows}


def has(word: str, text: str) -> bool:
    return bool(re.search(rf"(?<![ऀ-ॿ]){word}(?![ऀ-ॿ])", text))


def main() -> None:
    hindi, english = load("hi-IN"), load("en-US")
    counts: Counter[str] = Counter()
    examples: dict[str, list[tuple[str, str]]] = {}
    for key, row in hindi.items():
        if not has("कल", row["utt"]):
            continue
        en = english[key]["utt"].lower()
        label = "tomorrow" if "tomorrow" in en else "yesterday" if "yesterday" in en else "other"
        counts[label] += 1
        examples.setdefault(label, []).append((row["utt"], english[key]["utt"]))
    print(dict(counts))
    for label in ("tomorrow", "yesterday"):
        for hi, en in examples.get(label, [])[:2]:
            print(f"  {label}: {hi} | {en}")


if __name__ == "__main__":
    main()
