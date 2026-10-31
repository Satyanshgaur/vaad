"""Score the parsers on human-typed messages written from the scenario cards.

    uv run python scripts/eval_typed.py private/review/human_typed_texts.csv [--show]

The gold comes from the cards (docs/templates/scenario_cards.md), not from the writers: each card
fixes the amounts, weights, times and dates (relative to ``written_on``). The messages are private;
this prints aggregate numbers, and individual misses only with --show.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from vaad.canon.dates import find_dates
from vaad.canon.money import find_amounts
from vaad.canon.times import find_times
from vaad.canon.units import convert, find_quantities

D = date.fromisoformat


def gold(sid: str, w: date) -> dict[str, list[object]]:
    """Expected typed values for a card, with ``w`` the day the message was written."""
    day = lambda n: (w + timedelta(days=n)).isoformat()  # noqa: E731
    mon = day((0 - w.weekday()) % 7 or 7)  # the coming Monday
    spec: dict[str, dict[str, list[object]]] = {
        "S01": {"qty": [(1.5, "kg")], "date": [day(2)]},
        "S02": {"qty": [(2.5, "kg")], "date": [mon]},
        "S03": {"date": [day(1)]},
        "S04": {"money": [2500]}, "S05": {"money": [150000]}, "S06": {"money": [375]},
        "S07": {"money": [950], "date": [day((2 - w.weekday()) % 7 or 7)]},
        "S08": {"money": [399], "date": [day(1)]},
        "S09": {"money": [500000]}, "S10": {"money": [15000000]}, "S11": {"money": [666]},
        "S12": {"qty": [(0.5, "l")]},
        "S13": {"qty": [(1.5, "kg")]}, "S14": {"qty": [(2.5, "kg"), (750, "g")]},
        "S15": {"date": [mon], "time": ["09:30"]},
        "S16": {"date": [day(1)], "time": ["16:45"]},
        "S17": {"date": [D(f"{w.year}-{w.month % 12 + 1:02d}-03").isoformat()], "time": ["11:15"]},
        "S18": {"date": [day(2)]},
        "S19": {"date": [day((4 - w.weekday()) % 7 or 7)]},
        "S20": {"date": [day(1)], "time": ["19:30"]},
        "S21": {"date": [D(f"{w.year}-{w.month % 12 + 1:02d}-28").isoformat()], "time": ["10:00"]},
        "S22": {"date": [f"{w.year}-{w.month:02d}-01", day(-1)]},
        "S25": {"money": [12000]}, "S26": {"time": ["23:45"], "date": [w.isoformat()]},
        "S27": {"money": [599]}, "S28": {"money": [500]},
    }  # fmt: skip
    return spec.get(sid, {})


FIELD = {"Delivery": "delivery date", "Bill payment": "due date", "Appointment": "appointment",
         "Train": "booking departure", "Reminder": "reminder", "Statement": "statement history",
         "Travel": "booking departure"}  # fmt: skip


def outputs(
    text: str, w: date, field: str | None = None
) -> dict[str, list[tuple[object, float, tuple[object, ...]]]]:
    out: dict[str, list[tuple[object, float, tuple[object, ...]]]] = defaultdict(list)
    for a in find_amounts(text, require_marker=False):
        out["money"].append((a.value, a.confidence, ()))
    for q in find_quantities(text):
        out["qty"].append(((q.value, q.unit), q.confidence, ()))
        for target in ("kg", "l", "m"):  # the field names the unit it wants
            converted = convert(float(q.value), q.unit, target)
            if converted is not None and q.unit != target:
                out["qty"].append(((converted, target), q.confidence, ()))
    for d in find_dates(text, w, field):
        out["date"].append((d.value, d.confidence, d.alternatives))
    for t in find_times(text):
        out["time"].append((t.value, t.confidence, t.alternatives))
    return out


def same(a: object, b: object) -> bool:
    if isinstance(a, tuple) and isinstance(b, tuple):
        return same(a[0], b[0]) and a[1] == b[1]
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) < 1e-6
    return a == b


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--show", action="store_true")
    parser.add_argument(
        "--with-field", action="store_true", help="give dates the tool field's meaning"
    )
    args = parser.parse_args()
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    stat: dict[str, Counter[str]] = defaultdict(Counter)
    misses: list[str] = []
    for r in rows:
        text, w = r["utterance"].strip(), D(r["written_on"])
        if not text:
            continue
        out = outputs(text, w, FIELD.get(r["domain"]) if args.with_field else None)
        for kind, wanted in gold(r["id"], w).items():
            for exp in wanted:
                s = stat[kind]
                s["expected"] += 1
                hits = [(v, c, alts) for v, c, alts in out.get(kind, []) if same(v, exp)]
                alt_hits = [
                    1 for v, c, alts in out.get(kind, []) if any(same(a, exp) for a in alts)
                ]
                best = max((c for _, c, _ in hits), default=0.0)
                if best >= 0.9:
                    s["right and sure (>= 0.9: repairs a wrong value)"] += 1
                elif best >= 0.6:
                    s["right, moderate (0.6-0.9: passes if the model agrees)"] += 1
                elif hits:
                    s["right but would ask (< 0.6)"] += 1
                elif alt_hits:
                    s["ambiguous, right one offered"] += 1
                else:
                    s["missed"] += 1
                    misses.append(f"{r['id']} {kind} want {exp}: {text[:80]}")
        for kind, found in out.items():
            wanted = gold(r["id"], w).get(kind, [])
            for v, c, _ in found:
                if wanted and c >= 0.9 and not any(same(v, e) for e in wanted):
                    stat[kind]["confident but not on the card"] += 1
    print(f"{len(rows)} messages")
    for kind in ("money", "qty", "date", "time"):
        s = stat[kind]
        n = s["expected"]
        if n:
            print(f"\n{kind}: {n} expected values")
            for k, v in s.items():
                if k != "expected":
                    print(f"   {v:4d} ({v / n:5.1%})  {k}")
    if args.show:
        print("\nmisses:")
        print("\n".join(misses[:60]))


if __name__ == "__main__":
    main()
