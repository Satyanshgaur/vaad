#!/usr/bin/env bash
# One raw dev run with the restart-and-resume protection, for models added after the queue
# started.   scripts/run_one.sh NAME QUANT MODEL.gguf [harness flags...]
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
name="$1" quant="$2" model="$3"; shift 3
out="harness/reports/f1-${name}-${quant}/raw"
[ -f "$out/summary.json" ] && { echo "skip $name $quant (done)"; exit 0; }
mkdir -p "$out"
trap 'pgrep -x llama-server | xargs -r kill 2>/dev/null || true' EXIT
run_resilient "ensure_llama '$model' 8080 '$(dirname "$out")/server.log'" -- \
    --tasks harness/tasks/dev --base-url http://127.0.0.1:8080 \
    --model "$name" --quant "$quant" "$@" --out "$out"
