"""Export every lexicon entry to a CSV a native reviewer can check.

python scripts/export_lexicon_review.py private/review/lexicon_review.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent.parent / "src" / "vaad" / "canon" / "lexicons"
_COLUMNS = ["source_file", "section", "word", "value", "correct (yes/no)", "right_value", "comment"]


def _rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for path in sorted(_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for section, body in data.items():
            if isinstance(body, dict):
                for key, value in body.items():
                    if isinstance(value, dict):
                        value = ", ".join(map(str, value.values()))
                    rows.append([path.name, section, str(key), str(value), "", "", ""])
            elif isinstance(body, list):
                rows.extend([path.name, section, str(w), "", "", "", ""] for w in body)
    return rows


def main(out: str) -> None:
    with Path(out).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(_COLUMNS)
        w.writerows(_rows())


if __name__ == "__main__":
    main(sys.argv[1])
