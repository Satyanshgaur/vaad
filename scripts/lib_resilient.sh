# Helpers for long runs: start llama-server if it is not answering, and retry a resumable
# harness run when the server dies (a global out-of-memory kill took it down twice).
#   source scripts/lib_resilient.sh
ensure_llama() {  # ensure_llama MODEL.gguf PORT
  local model="$1" port="$2" log="${3:-/dev/null}"
  curl -sf "localhost:$port/health" >/dev/null && return 0
  pgrep -x llama-server | xargs -r kill 2>/dev/null || true
  sleep 2
  "$(dirname "${BASH_SOURCE[0]}")/llama_server.sh" "$model" "$port" >>"$log" 2>&1 &
  timeout 300 bash -c "until curl -sf localhost:$port/health >/dev/null; do sleep 2; done"
}
run_resilient() {  # run_resilient ENSURE_CMD -- HARNESS_ARGS...
  local ensure="$1"; shift 2
  for attempt in $(seq 1 15); do
    eval "$ensure"
    if uv run python -m harness.run "$@" --resume; then return 0; fi
    echo "run failed (attempt $attempt); restarting the backend and resuming" >&2
    sleep 5
  done
  return 1
}
