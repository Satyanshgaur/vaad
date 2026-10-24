#!/usr/bin/env bash
# Sync the private test split and task sources with the private repo.
#   scripts/private_sync.sh pull   # private repo -> working tree
#   scripts/private_sync.sh push   # working tree -> private repo (commit + push)
set -euo pipefail
REPO="${VAAD_PRIVATE_REPO:-git@github.com:Satyanshgaur/vaad-private.git}"
root="$(cd "$(dirname "$0")/.." && pwd)"
priv="$root/private"
[ -d "$priv/.git" ] || git clone -q "$REPO" "$priv"
git -C "$priv" pull -q --ff-only 2>/dev/null || true
case "${1:-}" in
  pull)
    mkdir -p "$root/harness/sources" "$root/harness/tasks/test"
    cp "$priv"/sources/*.yaml "$root/harness/sources/"
    cp "$priv"/tasks/test/*.jsonl "$root/harness/tasks/test/"
    (cd "$root" && uv run python -m harness.split check harness/tasks)
    ;;
  push)
    mkdir -p "$priv/sources" "$priv/tasks/test"
    cp "$root"/harness/sources/*.yaml "$priv/sources/"
    cp "$root"/harness/tasks/test/*.jsonl "$priv/tasks/test/"
    cp "$root/harness/tasks/SPLITS.lock" "$priv/tasks/"
    git -C "$priv" add -A
    git -C "$priv" commit -qm "${2:-sync from vaad $(git -C "$root" rev-parse --short HEAD)}" || true
    git -C "$priv" push -q origin HEAD
    ;;
  *) echo "usage: $0 pull|push [message]" >&2; exit 2 ;;
esac
