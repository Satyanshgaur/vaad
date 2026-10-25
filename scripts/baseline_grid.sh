#!/usr/bin/env bash
# Raw baseline (dev, seeds 0-3) for each model/quant, one llama-server at a time on port 8080.
#   scripts/baseline_grid.sh            # all entries below
# Each entry: name quant gguf-path-under-~/models extra-harness-flags
set -euo pipefail
MODELS="${MODELS_DIR:-$HOME/models}"
PORT=8080
GRID=(
  "qwen3.5-4b Q8_0 qwen3.5-4b/Qwen3.5-4B-Q8_0.gguf --no-think"
  "llama3.2-3b Q4_K_M llama3.2-3b/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
  "llama3.2-3b Q8_0 llama3.2-3b/Llama-3.2-3B-Instruct-Q8_0.gguf"
)
stop_server() {
  local pid
  for pid in $(pgrep -x llama-server || true); do
    kill "$pid"; while kill -0 "$pid" 2>/dev/null; do sleep 0.5; done
  done
}
trap stop_server EXIT
for entry in "${GRID[@]}"; do
  read -r name quant file extra <<<"$entry"
  out="harness/reports/g0-${name}-${quant}/raw-a"
  if [ -f "$out/summary.json" ]; then echo "skip $name $quant (done)"; continue; fi
  stop_server
  mkdir -p "$(dirname "$out")"
  "$(dirname "$0")/llama_server.sh" "$MODELS/$file" "$PORT" >"$(dirname "$out")/server.log" 2>&1 &
  timeout 180 bash -c "until curl -sf localhost:$PORT/health >/dev/null; do sleep 1; done"
  echo "=== $name $quant ($(date +%T))"
  # shellcheck disable=SC2086
  uv run python -m harness.run --tasks harness/tasks/dev --base-url "http://127.0.0.1:$PORT" \
      --model "$name" --quant "$quant" $extra --out "$out"
done
