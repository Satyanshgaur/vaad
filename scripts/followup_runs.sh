#!/usr/bin/env bash
# Raw dev runs for the pre-registered follow-up (docs/PREREG.md): one llama-server at a time,
# seeds 0-3, temperature 0.7. Skips finished runs and waits for model files that are still
# downloading or being quantized.
#   scripts/followup_runs.sh [name ...]      (default: all)
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
MODELS="${MODELS_DIR:-$HOME/models}"
PORT=8080
# name quant file flags
GRID=(
  "qwen3.5-4b Q4_K_M qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf --no-think"
  "granite-4.0-micro Q4_K_M granite-4.0-micro/granite-4.0-micro-Q4_K_M.gguf"
  "phi-4-mini Q4_K_M phi-4-mini/Phi-4-mini-instruct-Q4_K_M.gguf"
  "llama3.2-3b Q4_K_M llama3.2-3b/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
  "qwen3.5-4b-noimat Q4_K_M qwen3.5-4b-noimat/Qwen3.5-4B-Q4_K_M-noimat.gguf --no-think"
  "qwen3.5-4b-noimat Q3_K_M qwen3.5-4b-noimat/Qwen3.5-4B-Q3_K_M-noimat.gguf --no-think"
  "qwen3.5-0.8b Q8_0 qwen3.5-0.8b/Qwen3.5-0.8B-Q8_0.gguf --no-think"
)
# The grammar ablation owns the GPU until its loose run finishes.
until [ -f harness/reports/g1-loose/summary.json ]; do sleep 60; done
want=("$@")
stop_server() { pgrep -x llama-server | xargs -r kill 2>/dev/null || true; sleep 2; }
trap stop_server EXIT
for entry in "${GRID[@]}"; do
  read -r name quant file extra <<<"$entry"
  if [ ${#want[@]} -gt 0 ] && [[ ! " ${want[*]} " =~ " $name " ]]; then continue; fi
  out="harness/reports/f1-${name}-${quant}/raw"
  [ -f "$out/summary.json" ] && { echo "skip $name $quant (done)"; continue; }
  until [ -f "$MODELS/$file" ] && ! pgrep -x llama-quantize >/dev/null; do sleep 30; done
  mkdir -p "$out"
  echo "=== $name $quant ($(date +%T))"
  # shellcheck disable=SC2086
  run_resilient "ensure_llama '$MODELS/$file' $PORT '$(dirname "$out")/server.log'" -- \
      --tasks harness/tasks/dev --base-url "http://127.0.0.1:$PORT" \
      --model "$name" --quant "$quant" $extra --out "$out"
  stop_server
done
