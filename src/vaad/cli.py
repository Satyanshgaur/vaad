"""Command-line entry point."""

from __future__ import annotations

import argparse
from typing import Any

from vaad import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vaad", description=__doc__)
    parser.add_argument("--version", action="version", version=f"vaad {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run the OpenAI-compatible gateway")
    serve.add_argument("--config", default="config/vaad.yaml")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    gaps = sub.add_parser("gaps", help="list unknown words before time/money/quantity anchors")
    gaps.add_argument("csv")
    gaps.add_argument("--column", default="text")
    gaps.add_argument("--min-count", type=int, default=3)

    parse = sub.add_parser("parse", help="show every value found in a Hindi/Hinglish text")
    parse.add_argument("text")
    parse.add_argument("--ref-date", default=None, help="YYYY-MM-DD for kal/parso; default today")

    args = parser.parse_args(argv)
    if args.command == "parse":
        import json
        from datetime import date

        from vaad.canon import annotate_turn
        from vaad.canon.dates import find_dates
        from vaad.canon.money import find_amounts
        from vaad.canon.numbers import find_numbers
        from vaad.canon.times import find_durations, find_times
        from vaad.canon.units import find_quantities

        ref = date.fromisoformat(args.ref_date) if args.ref_date else date.today()
        found: list[tuple[str, list[Any]]] = [
            ("number", find_numbers(args.text)),
            ("time", find_times(args.text)),
            ("duration", find_durations(args.text)),
            ("date", find_dates(args.text, ref)),
            ("quantity", find_quantities(args.text)),
        ]
        values = [
            {"kind": kind, "text": args.text[m.start : m.end], "value": m.value,
             "confidence": m.confidence, "reason": m.reason}
            for kind, matches in found
            for m in matches
        ]  # fmt: skip
        for a in find_amounts(args.text):
            sp = a.source
            text = args.text[sp.start : sp.end] if sp else ""
            values.append(
                {"kind": "amount", "text": text, "value": a.value,
                 "confidence": a.confidence, "reason": a.reason}
            )  # fmt: skip
        out = {"annotated": annotate_turn(args.text, ref), "values": values}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "gaps":
        import json

        from vaad.canon.gaps import mine, read_column

        report = mine(read_column(args.csv, args.column), args.min_count)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "serve":
        import uvicorn

        from vaad.config import load_settings
        from vaad.server.app import create_app

        uvicorn.run(create_app(load_settings(args.config)), host=args.host, port=args.port)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
