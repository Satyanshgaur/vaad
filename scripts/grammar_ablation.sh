#!/usr/bin/env bash
# Phase 1 / G1: dev split through the gateway with a strict and a loose date grammar.
#   scripts/grammar_ablation.sh [strict|loose ...]     (default: both)
# One llama-server (Qwen3.5-4B Q4_K_M, GPU) on 8080, the gateway on 8100. Results go to
# harness/reports/g1-<mode>/. Compare with the raw baseline in harness/reports/g0-*/.
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
MODELS="${MODELS_DIR:-$HOME/models}"
modes=("$@")
[ ${#modes[@]} -gt 0 ] || modes=(strict loose)
work="$(mktemp -d)"
gw=""
cleanup() {
  [ -z "$gw" ] || kill "$gw" 2>/dev/null || true
  pgrep -x llama-server | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT
pgrep -x llama-server | xargs -r kill 2>/dev/null || true
model="$MODELS/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
ensure_llama "$model" 8080 "$work/llama.log"
for mode in "${modes[@]}"; do
  out="harness/reports/g1-$mode"
  [ -f "$out/summary.json" ] && { echo "skip $mode (done)"; continue; }
  mkdir -p "$out"
  cat >"$work/$mode.yaml" <<EOF
gateway_enabled: true
small: {url: "http://127.0.0.1:8080", model: qwen3.5-4b}
grammar: {date_grammar: $mode}
trace_path: $out/gateway-trace.jsonl
EOF
  ensure_gateway() {
    curl -sf localhost:8100/healthz >/dev/null && return 0
    [ -z "$gw" ] || kill "$gw" 2>/dev/null || true
    .venv/bin/vaad serve --config "$work/$mode.yaml" --port 8100 >>"$work/vaad-$mode.log" 2>&1 &
    gw=$!
    timeout 60 bash -c 'until curl -sf localhost:8100/healthz >/dev/null; do sleep 1; done'
  }
  echo "=== grammar date=$mode ($(date +%T))"
  run_resilient "ensure_llama '$model' 8080 '$work/llama.log'; ensure_gateway" -- \
      --tasks harness/tasks/dev --base-url http://127.0.0.1:8100 \
      --model qwen3.5-4b --quant Q4_K_M --gateway "grammar-$mode" --no-think --out "$out"
  kill "$gw" 2>/dev/null || true; wait "$gw" 2>/dev/null || true
  gw=""
done
