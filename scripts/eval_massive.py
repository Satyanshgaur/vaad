"""Evaluate the time and date parsers on MASSIVE hi-IN with gold from the English parallel.

    uv run python scripts/eval_massive.py --partition train     # develop against this
    uv run python scripts/eval_massive.py --partition dev       # sanity check
    uv run python scripts/eval_massive.py --partition test      # once, after the parsers are frozen

Gold is independent of our lexicons: "कल" is tomorrow or yesterday according to the English text
of the same utterance, and a clock time's gold comes from the English slot ("nine a. m.").
Needs `scripts/fetch_open_data.sh` first.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

from vaad.canon.dates import find_dates
from vaad.canon.times import find_times

ROOT = Path(os.environ.get("OPEN_DATA", Path.home() / "opendata"))
REF = date(2026, 10, 24)  # a Saturday; any fixed date works
_NUMBER_WORDS = "zero one two three four five six seven eight nine ten eleven twelve"
_NUM = {w: i for i, w in enumerate(_NUMBER_WORDS.split())}
_MIN = {"fifteen": 15, "thirty": 30, "forty five": 45, "twenty": 20, "ten": 10, "five": 5}
_SLOT = re.compile(r"\[(\w+) : ([^\]]+)\]")


def load(locale: str) -> dict[str, dict[str, str]]:
    path = glob.glob(str(ROOT / f"massive/*/data/{locale}.jsonl"))[0]
    return {r["id"]: r for r in map(json.loads, Path(path).read_text("utf-8").splitlines())}


def english_clock(slot: str) -> set[str] | None:
    """Acceptable 24-hour readings of an English clock slot, or None if it is not a clock time."""
    s = slot.lower().replace(".", "").replace("'", "").strip()
    m = re.fullmatch(
        r"(?:(?:at|by)\s+)?(?P<h>\d{1,2}|" + "|".join(_NUM) + r")(?:\s+(?P<min>fifteen|thirty|"
        r"forty five|twenty|ten|five|\d{2}))?\s*(?P<ap>a m|p m|am|pm|oclock|o clock)?",
        s,
    )
    if not m:
        return None
    h = int(m["h"]) if m["h"].isdigit() else _NUM[m["h"]]
    minute = 0
    if m["min"]:
        minute = int(m["min"]) if m["min"].isdigit() else _MIN[m["min"]]
    if m["ap"] is None and not m["min"] and m["h"] in _NUM and len(s.split()) == 1:
        return None  # a bare number: not clearly a time
    if not 1 <= h <= 12:
        return None
    ap = (m["ap"] or "").replace(" ", "")
    if ap in ("am", "pm"):
        hour = h % 12 + (12 if ap == "pm" else 0)
        return {f"{hour:02d}:{minute:02d}"}
    return {f"{h % 12:02d}:{minute:02d}", f"{h % 12 + 12:02d}:{minute:02d}"}


def kal(hi: dict[str, dict[str, str]], en: dict[str, dict[str, str]], partition: str) -> None:
    rows = []
    for key, row in hi.items():
        if row["partition"] != partition or not re.search(r"(?<![ऀ-ॿ])कल(?![ऀ-ॿ])", row["utt"]):
            continue
        english = en[key]["utt"].lower()
        gold = 1 if "tomorrow" in english else -1 if "yesterday" in english else 0
        if gold:
            rows.append((row["utt"], gold))
    decided = correct = abstain = 0
    errors = []
    for utt, gold in rows:
        matches = [m for m in find_dates(utt, REF) if "कल" in utt[m.start : m.end]]
        if not matches:
            continue
        m = matches[0]
        if m.confidence < 0.6:
            abstain += 1
            continue
        decided += 1
        predicted = 1 if date.fromisoformat(m.value) > REF else -1
        if predicted == gold:
            correct += 1
        else:
            errors.append((utt, gold, m.reason))
    n = len(rows)
    tomorrow = sum(1 for _, g in rows if g == 1)
    print(f"\n'kal' ({partition}): {n} utterances, {tomorrow} tomorrow / {n - tomorrow} yesterday")
    print(f"  always-tomorrow baseline accuracy: {tomorrow / n:.1%}")
    print(f"  decided {decided} ({decided / n:.1%}), abstained {abstain} ({abstain / n:.1%}), "
          f"missed {n - decided - abstain}")  # fmt: skip
    if decided:
        print(f"  accuracy when decided: {correct / decided:.1%}  ({correct}/{decided})")
    for utt, gold, why in errors[:6]:
        print(f"    wrong ({'tomorrow' if gold > 0 else 'yesterday'}): {utt}  [{why}]")


def clock(hi: dict[str, dict[str, str]], en: dict[str, dict[str, str]], partition: str) -> None:
    total = hit = confident = confident_hit = none = 0
    bad = []
    for key, row in hi.items():
        if row["partition"] != partition:
            continue
        hi_slots = [v for k, v in _SLOT.findall(row["annot_utt"]) if k == "time"]
        en_slots = [v for k, v in _SLOT.findall(en[key]["annot_utt"]) if k == "time"]
        if len(hi_slots) != len(en_slots):
            continue
        for h, e in zip(hi_slots, en_slots, strict=True):
            gold = english_clock(e)
            if gold is None:
                continue
            total += 1
            full = row["utt"]
            at = full.find(h)
            found = find_times(full)
            if at < 0:
                continue  # the slot text is not a substring of the utterance (spacing differs)
            found = [t for t in found if t.start < at + len(h) and at < t.end]
            if not found:
                none += 1
                bad.append((h, e, "no time found"))
                continue
            t = found[0]
            ok = t.value in gold or any(a in gold for a in t.alternatives)
            hit += ok
            if t.confidence >= 0.9:
                confident += 1
                confident_hit += t.value in gold
            if not ok:
                bad.append((h, e, f"{t.value} vs {sorted(gold)}"))
    print(f"\nclock times ({partition}): {total} slots with an English clock reading")
    print(f"  parsed with the right value among its readings: {hit} ({hit / total:.1%}); "
          f"nothing found: {none}")  # fmt: skip
    if confident:
        print(f"  confident (>= 0.9) and exactly right: {confident_hit}/{confident} "
              f"({confident_hit / confident:.1%})")  # fmt: skip
    print(f"  confident share: {confident / total:.1%}")
    for h, e, why in bad[:8]:
        print(f"    miss: {h} | {e} | {why}")


def dates_coverage(hi: dict[str, dict[str, str]], partition: str) -> None:
    c: Counter[str] = Counter()
    for row in hi.values():
        if row["partition"] != partition:
            continue
        for kind, span in _SLOT.findall(row["annot_utt"]):
            if kind == "date":
                c["date slots"] += 1
                if find_dates(span, REF):
                    c["with a parsed date"] += 1
    parsed, total = c["with a parsed date"], max(1, c["date slots"])
    print(f"\ndate slots ({partition}): {c['date slots']}, parsed {parsed} ({parsed / total:.1%})")
    print("  (week and month words such as 'इस सप्ताह' are not dates here)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", default="train", choices=["train", "dev", "test"])
    args = parser.parse_args()
    hi, en = load("hi-IN"), load("en-US")
    kal(hi, en, args.partition)
    clock(hi, en, args.partition)
    dates_coverage(hi, args.partition)


if __name__ == "__main__":
    main()
