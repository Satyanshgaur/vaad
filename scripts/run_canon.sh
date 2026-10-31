#!/usr/bin/env bash
# H9 (docs/PREREG.md, amendment A5): the canonicalizer modes through the gateway on dev.
#   scripts/run_canon.sh [qwen granite ministral]       one llama-server at a time, restart+resume
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
MODELS="${MODELS_DIR:-$HOME/models}"
declare -A FILE=([qwen]="qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
                 [granite]="granite-4.0-micro/granite-4.0-micro-Q4_K_M.gguf"
                 [ministral]="ministral-3-3b/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf")
declare -A NAME=([qwen]=qwen3.5-4b [granite]=granite-4.0-micro [ministral]=ministral-3-3b)
declare -A FLAGS=([qwen]="--no-think" [granite]="" [ministral]="")
want=("$@"); [ ${#want[@]} -gt 0 ] || want=(qwen granite ministral)
work="$(mktemp -d)"; gw=""
cleanup() { [ -z "$gw" ] || kill "$gw" 2>/dev/null || true; pgrep -x llama-server | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT
for m in "${want[@]}"; do
  model="$MODELS/${FILE[$m]}"
  for mode in off annotate verify both; do
    out="harness/reports/h9-${NAME[$m]}-$mode"
    [ -f "$out/summary.json" ] && { echo "skip $m $mode (done)"; continue; }
    mkdir -p "$out"
    cat >"$work/$mode.yaml" <<EOF
gateway_enabled: true
small: {url: "http://127.0.0.1:8080", model: ${NAME[$m]}}
grammar: {enabled: false, retry: true}
canon: {mode: $mode, ref_date: "2026-10-24"}
trace_path: $out/gateway-trace.jsonl
EOF
    ensure_gateway() {
      curl -sf localhost:8100/healthz >/dev/null && return 0
      [ -z "$gw" ] || kill "$gw" 2>/dev/null || true
      .venv/bin/vaad serve --config "$work/$mode.yaml" --port 8100 >>"$work/vaad.log" 2>&1 &
      gw=$!
      timeout 60 bash -c 'until curl -sf localhost:8100/healthz >/dev/null; do sleep 1; done'
    }
    echo "=== $m canon=$mode ($(date +%T))"
    run_resilient "ensure_llama '$model' 8080 '$work/llama.log'; ensure_gateway" -- \
        --tasks harness/tasks/dev --base-url http://127.0.0.1:8100 --model "${NAME[$m]}" \
        --quant Q4_K_M ${FLAGS[$m]} --gateway "canon-$mode" --source value_heavy bfcl_en --out "$out"
    kill "$gw" 2>/dev/null || true; wait "$gw" 2>/dev/null || true; gw=""
  done
  pgrep -x llama-server | xargs -r kill 2>/dev/null || true; sleep 2
done
