#!/usr/bin/env bash
# Open datasets used for prevalence counts and for the time/date evaluation (docs/OPEN_DATA.md).
# All CC BY 4.0. Downloads to ~/opendata (outside the repo; do not commit them).
set -euo pipefail
DEST="${OPEN_DATA:-$HOME/opendata}"
mkdir -p "$DEST/massive" "$DEST/comi" "$DEST/fleurs"
[ -f "$DEST/massive/massive.tar.gz" ] || {
  curl -sSfL -o "$DEST/massive/massive.tar.gz" \
    https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz
  tar -xzf "$DEST/massive/massive.tar.gz" -C "$DEST/massive"
}
hf download LingoIITGN/COMI-LINGUA TN_train.csv --repo-type dataset --local-dir "$DEST/comi"
hf download google/fleurs data/hi_in/train.tsv data/hi_in/dev.tsv data/hi_in/test.tsv \
  --repo-type dataset --local-dir "$DEST/fleurs"
