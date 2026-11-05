#!/usr/bin/env bash
# The one test-split run (docs/PREREG.md, amendment A7).
#   scripts/run_phase4.sh [qwen granite ministral]     one llama-server at a time, restart+resume
# Do not edit src/ or the lexicons while this runs. Reports go to harness/reports/p4-<model>-<arm>.
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
MODELS="${MODELS_DIR:-$HOME/models}"
declare -A FILE=([qwen]="qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
                 [granite]="granite-4.0-micro/granite-4.0-micro-Q4_K_M.gguf"
                 [ministral]="ministral-3-3b/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf")
declare -A NAME=([qwen]=qwen3.5-4b [granite]=granite-4.0-micro [ministral]=ministral-3-3b)
declare -A FLAGS=([qwen]="--no-think" [granite]="" [ministral]="")
SOURCES=(--source value_heavy bfcl_en bfcl_hinglish)
want=("$@"); [ ${#want[@]} -gt 0 ] || want=(qwen granite ministral)
echo "commit $(git rev-parse HEAD)" | tee harness/reports/p4-commit.txt
work="$(mktemp -d)"; gw=""
cleanup() { [ -z "$gw" ] || kill "$gw" 2>/dev/null || true; pgrep -x llama-server | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT
for m in "${want[@]}"; do
  model="$MODELS/${FILE[$m]}"
  arms=(off annotate both); [ "$m" = qwen ] && arms+=(worked)
  for arm in "${arms[@]}"; do
    out="harness/reports/p4-${NAME[$m]}-$arm"
    [ -f "$out/summary.json" ] && { echo "skip $m $arm (done)"; continue; }
    mkdir -p "$out"
    echo "=== $m $arm ($(date +%T))"
    if [ "$arm" = worked ]; then
      run_resilient "ensure_llama '$model' 8080 '$work/llama.log'" -- \
          --tasks harness/tasks/test --base-url http://127.0.0.1:8080 --model "${NAME[$m]}" \
          --quant Q4_K_M ${FLAGS[$m]} --gateway worked "${SOURCES[@]}" \
          --system-prompt harness/prompts/worked_conversions.txt --out "$out"
      continue
    fi
    cat >"$work/$arm.yaml" <<EOF
gateway_enabled: true
small: {url: "http://127.0.0.1:8080", model: ${NAME[$m]}}
grammar: {enabled: false, retry: true}
canon: {mode: "$arm", ref_date: "2026-10-24"}
trace_path: $out/gateway-trace.jsonl
EOF
    ensure_gateway() {
      curl -sf localhost:8100/healthz >/dev/null && return 0
      [ -z "$gw" ] || kill "$gw" 2>/dev/null || true
      .venv/bin/vaad serve --config "$work/$arm.yaml" --port 8100 >>"$work/vaad.log" 2>&1 &
      gw=$!
      timeout 60 bash -c 'until curl -sf localhost:8100/healthz >/dev/null; do sleep 1; done'
    }
    run_resilient "ensure_llama '$model' 8080 '$work/llama.log'; ensure_gateway" -- \
        --tasks harness/tasks/test --base-url http://127.0.0.1:8100 --model "${NAME[$m]}" \
        --quant Q4_K_M ${FLAGS[$m]} --gateway "canon-$arm" "${SOURCES[@]}" --out "$out"
    kill "$gw" 2>/dev/null || true; wait "$gw" 2>/dev/null || true; gw=""
  done
  pgrep -x llama-server | xargs -r kill 2>/dev/null || true; sleep 2
done
