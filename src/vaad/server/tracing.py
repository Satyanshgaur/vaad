"""JSON-lines trace writer; the harness reads these files."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from vaad.types import Trace


def write_trace(trace: Trace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(trace), ensure_ascii=False) + "\n")
