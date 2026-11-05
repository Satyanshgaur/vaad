"""Command-line entry point."""

from __future__ import annotations

import argparse

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

    args = parser.parse_args(argv)
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
