"""Reliability card: how often each parser is right at each confidence level.

    uv run python scripts/calibration_card.py --typed PRIVATE.csv [--massive-partition test]

Aggregates only: counts and rates, never message text. For a trustworthy "ask when unsure"
layer, the confidence a parser reports has to mean something: outputs at >= 0.9 should be
right about as often as the number says. Sources: MASSIVE hi-IN (public; "kal" direction and
clock times, gold from the English parallel) and a private card-driven typed batch (gold from
the cards, see eval_typed.py).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

import eval_massive as M
import eval_typed as T

from vaad.canon.dates import find_dates
from vaad.canon.times import find_times

BANDS = (("< 0.6 (asks)", 0.0, 0.6), ("0.6 - 0.9", 0.6, 0.9), (">= 0.9 (sure)", 0.9, 1.01))
Table = dict[str, dict[str, list[int]]]  # parser -> band -> [correct, total]


def band(conf: float) -> str:
    return next(name for name, lo, hi in BANDS if lo <= conf < hi)


def add(table: Table, parser: str, conf: float, ok: bool) -> None:
    cell = table[parser].setdefault(band(conf), [0, 0])
    cell[0] += ok
    cell[1] += 1


def massive(table: Table, partition: str) -> None:
    hi, en = M.load("hi-IN"), M.load("en-US")
    for key, row in hi.items():
        if row["partition"] != partition:
            continue
        english = en[key]["utt"].lower()
        gold_dir = 1 if "tomorrow" in english else -1 if "yesterday" in english else 0
        if gold_dir and M.re.search(r"(?<![ऀ-ॿ])कल(?![ऀ-ॿ])", row["utt"]):
            hits = [m for m in find_dates(row["utt"], M.REF) if "कल" in row["utt"][m.start : m.end]]
            if hits:
                predicted = 1 if date.fromisoformat(hits[0].value) > M.REF else -1
                add(table, "MASSIVE: kal direction", hits[0].confidence, predicted == gold_dir)
        hi_slots = [v for k, v in M._SLOT.findall(row["annot_utt"]) if k == "time"]
        en_slots = [v for k, v in M._SLOT.findall(en[key]["annot_utt"]) if k == "time"]
        if len(hi_slots) != len(en_slots):
            continue
        for h, e in zip(hi_slots, en_slots, strict=True):
            gold = M.english_clock(e)
            at = row["utt"].find(h)
            if gold is None or at < 0:
                continue
            for t in find_times(row["utt"]):
                if t.start < at + len(h) and at < t.end:
                    add(table, "MASSIVE: clock time", t.confidence, t.value in gold)
                    break


def typed(table: Table, path: Path, label: str) -> None:
    for r in csv.DictReader(path.open(encoding="utf-8-sig", newline="")):
        text, w = r["utterance"].strip(), date.fromisoformat(r["written_on"])
        if not text:
            continue
        wanted = T.gold(r["id"], w)
        out = T.outputs(text, w, T.FIELD.get(r["domain"]))
        names = {"money": "amount", "qty": "quantity", "date": "date", "time": "clock time"}
        for kind, found in out.items():
            if kind not in wanted:
                continue  # the card has no such value; not scored
            for value, conf, _ in found:
                add(
                    table,
                    f"{label}: {names[kind]}",
                    conf,
                    any(T.same(value, e) for e in wanted[kind]),
                )


def render(table: Table) -> str:
    lines = ["| Parser | " + " | ".join(name for name, _, _ in BANDS) + " |", "|---|---|---|---|"]
    for parser in sorted(table):
        cells = []
        for name, _, _ in BANDS:
            c, n = table[parser].get(name, [0, 0])
            cells.append(f"{c / n:.0%} ({c}/{n})" if n else "-")
        lines.append(f"| {parser} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed", type=Path, nargs="*", default=[])
    parser.add_argument("--labels", nargs="*", default=[])
    parser.add_argument("--massive-partition", default="test")
    args = parser.parse_args()
    table: Table = defaultdict(dict)
    massive(table, args.massive_partition)
    for path, label in zip(
        args.typed, args.labels or [f"typed {i + 1}" for i in range(len(args.typed))], strict=False
    ):
        typed(table, path, label)
    print(render(table))


if __name__ == "__main__":
    main()
