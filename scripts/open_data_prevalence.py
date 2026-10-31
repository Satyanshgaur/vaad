"""How often spoken-form numbers appear in open Hindi and Hinglish text (docs/OPEN_DATA.md).

Run `scripts/fetch_open_data.sh` first, then `uv run python scripts/open_data_prevalence.py`.

Counts use canon.numbers.find_numbers, so they inherit its limits: "ek" and "do" are counted as
plain number words even though some are articles or verbs, and nothing is validated by a human.
These are rough prevalence figures, not gold labels.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
from collections import Counter
from pathlib import Path

from vaad.canon.numbers import find_numbers

ROOT = Path(os.environ.get("OPEN_DATA", Path.home() / "opendata"))
DIGIT = re.compile(r"[0-9०-९]")  # noqa: RUF001
FRACTION = re.compile(r"sava|saade|sade|paune|dedh|dhai|aadha|सवा|साढ़े|साढे|पौने|डेढ़|ढाई|आधा", re.I)
MULTIPLIER = re.compile(r"sau|hazaar|lakh|lac|crore|सौ|हज़ार|हजार|लाख|करोड़", re.I)


def kinds(text: str) -> set[str]:
    out: set[str] = set()
    for m in find_numbers(text):
        seg = text[m.start : m.end]
        if DIGIT.search(seg):
            out.add("digits")
        elif FRACTION.search(seg):
            out.add("fraction word (dedh, dhai, sava, saade, paune, aadha)")
        elif MULTIPLIER.search(seg):
            out.add("word + sau/hazaar/lakh/crore")
        else:
            out.add("plain number word")
    return out


def report(name: str, texts: list[str]) -> None:
    counts: Counter[str] = Counter()
    anything = 0
    for text in texts:
        found = kinds(text)
        anything += bool(found)
        counts.update(found)
    n = len(texts)
    print(f"\n{name}: {n} texts, with any number {anything} ({anything / n:.1%})")
    for kind, count in counts.most_common():
        print(f"  {count:6d} ({count / n:5.1%})  {kind}")


def main() -> None:
    massive = [
        json.loads(line)
        for line in Path(glob.glob(str(ROOT / "massive/*/data/hi-IN.jsonl"))[0])
        .read_text("utf-8")
        .splitlines()
    ]
    report("MASSIVE hi-IN (voice-assistant commands)", [r["utt"] for r in massive])
    report("  with a time slot", [r["utt"] for r in massive if "[time :" in r["annot_utt"]])
    report(
        "  with a currency slot",
        [r["utt"] for r in massive if "[currency_name :" in r["annot_utt"]],
    )
    csv.field_size_limit(10**9)
    with (ROOT / "comi/TN_train.csv").open(encoding="utf-8") as f:
        report(
            "COMI-LINGUA TN (social-media Hinglish, Roman)",
            [r["Sentences"] for r in csv.DictReader(f)],
        )
    fleurs = [
        line.rstrip("\n").split("\t")
        for line in (ROOT / "fleurs/data/hi_in/train.tsv").read_text("utf-8").splitlines()
    ]
    report("FLEURS hi_in (read Wikipedia sentences)", [row[3] for row in fleurs])


if __name__ == "__main__":
    main()
