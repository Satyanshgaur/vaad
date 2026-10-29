"""Calibration texts for the imatrix arms of H8 (docs/PREREG.md, amendment A3).

English  : English Wikipedia paragraphs.
Indic    : Hindi Wikipedia paragraphs, half in Devanagari and half romanized with
           harness/romanize.py (the Roman-script half stands in for Hinglish typing).
Both are sized to the same number of model tokens (80 chunks of 512). No task text or
evaluation data is used. Sampling is seeded.

    uv run --with pyarrow python scripts/make_calibration.py --en EN.parquet --hi HI.parquet \
        --model ~/models/qwen3.5-4b-src/Qwen3.5-4B-BF16.gguf --out data/calibration
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.romanize import romanize_hindi

SEED = 20261031
TARGET_TOKENS = 80 * 512
TOKENIZE = Path.home() / "tools/llama.cpp/build/bin/llama-tokenize"


def count_tokens(model: Path, text: str, tmp: Path) -> int:
    tmp.write_text(text, encoding="utf-8")
    out = subprocess.run(
        [str(TOKENIZE), "-m", str(model), "-f", str(tmp), "--ids", "--no-bos", "--log-disable"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return out.count(",") + 1 if out.strip() else 0


def paragraphs(path: Path, rng: random.Random, limit: int) -> list[str]:
    table = pq.read_table(path, columns=["text"])
    rows = table.column("text").to_pylist()
    rng.shuffle(rows)
    out: list[str] = []
    for text in rows[:limit]:
        out += [p.strip() for p in text.split("\n") if 200 <= len(p.strip()) <= 1500]
    rng.shuffle(out)
    return out


def build(paras: list[str], model: Path, tmp: Path, transform=lambda s: s) -> str:  # type: ignore[no-untyped-def]
    """Add paragraphs until the token budget is met (measured every 20 paragraphs)."""
    chosen: list[str] = []
    for p in paras:
        chosen.append(transform(p))
        if len(chosen) % 20 == 0 and count_tokens(model, "\n\n".join(chosen), tmp) >= TARGET_TOKENS:
            break
    return "\n\n".join(chosen)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--en", type=Path, required=True)
    parser.add_argument("--hi", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    tmp = args.out / ".tmp.txt"

    english = build(paragraphs(args.en, rng, 3000), args.model, tmp)
    hindi = paragraphs(args.hi, rng, 6000)
    half = len(hindi) // 2
    # half the budget in Devanagari, half in the same style romanized
    devanagari = build(hindi[:half], args.model, tmp)
    romanized = build(hindi[half:], args.model, tmp, romanize_hindi)

    # trim each half to half the budget by tokens, then join
    def cut(text: str) -> str:
        parts = text.split("\n\n")
        keep: list[str] = []
        for part in parts:
            keep.append(part)
            if (
                len(keep) % 10 == 0
                and count_tokens(args.model, "\n\n".join(keep), tmp) >= TARGET_TOKENS // 2
            ):
                break
        return "\n\n".join(keep)

    indic = cut(devanagari) + "\n\n" + cut(romanized)
    (args.out / "calibration_en.txt").write_text(english, encoding="utf-8")
    (args.out / "calibration_indic.txt").write_text(indic, encoding="utf-8")
    tmp.unlink(missing_ok=True)
    for name, text in (("en", english), ("indic", indic)):
        print(name, len(text), "chars,", count_tokens(args.model, text, tmp), "tokens")
    tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
