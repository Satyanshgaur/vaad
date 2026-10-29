#!/usr/bin/env bash
# Pre-registered A3 runs (docs/PREREG.md): per qualifying model, the script control (romanized
# Hindi), translate-first, the strong prompt and the worked-conversion prompt on dev.
#   scripts/run_h6_h7.sh [model ...]     (default: qwen granite ministral)
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
MODELS="${MODELS_DIR:-$HOME/models}"
declare -A FILE=(
  [qwen]="qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
  [granite]="granite-4.0-micro/granite-4.0-micro-Q4_K_M.gguf"
  [ministral]="ministral-3-3b/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
)
declare -A NAME=([qwen]=qwen3.5-4b [granite]=granite-4.0-micro [ministral]=ministral-3-3b)
declare -A FLAGS=([qwen]="--no-think" [granite]="" [ministral]="")
want=("$@"); [ ${#want[@]} -gt 0 ] || want=(qwen granite ministral)
trap 'pgrep -x llama-server | xargs -r kill 2>/dev/null || true' EXIT
for m in "${want[@]}"; do
  model="$MODELS/${FILE[$m]}"
  common=(--tasks harness/tasks/dev --base-url http://127.0.0.1:8080 --model "${NAME[$m]}" --quant Q4_K_M ${FLAGS[$m]})
  run() {  # run LABEL ARGS...
    local label="$1"; shift
    local out="harness/reports/h67-${NAME[$m]}-${label}"
    [ -f "$out/summary.json" ] && { echo "skip $m $label (done)"; return; }
    mkdir -p "$out"
    echo "=== $m $label ($(date +%T))"
    run_resilient "ensure_llama '$model' 8080 '$out/../h67-${NAME[$m]}-server.log'" -- \
        "${common[@]}" --gateway "$label" "$@" --out "$out"
  }
  run roman     --lang hi --preprocess romanize
  run translate --lang hi hinglish --preprocess translate
  run strong    --source value_heavy bfcl_en bfcl_hinglish --system-prompt harness/prompts/strong_system.txt
  run worked    --source value_heavy bfcl_en bfcl_hinglish --system-prompt harness/prompts/worked_conversions.txt
  pgrep -x llama-server | xargs -r kill 2>/dev/null || true; sleep 2
done
