#!/usr/bin/env bash
# Start llama-server for the harness: native tool calling (--jinja), all layers on GPU.
#   scripts/llama_server.sh ~/models/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf [port]
# Env: LLAMA_CPP (default ~/tools/llama.cpp), CTX (default 8192), NGL (default 99).
set -euo pipefail
model="${1:?usage: $0 MODEL.gguf [port]}"
port="${2:-8080}"
bin="${LLAMA_CPP:-$HOME/tools/llama.cpp}/build/bin/llama-server"
exec "$bin" -m "$model" --jinja -ngl "${NGL:-99}" -c "${CTX:-8192}" \
    --host 127.0.0.1 --port "$port" --no-webui
