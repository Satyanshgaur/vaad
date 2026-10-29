#!/usr/bin/env bash
# Controlled quants for H4 (docs/PREREG.md): Qwen3.5-4B from the BF16 GGUF with llama-quantize
# and NO importance matrix, so Q4_K_M and Q3_K_M differ only in bit width. Without an imatrix
# Q3_K_M is harsher than most published Q3 files.
set -euo pipefail
MODELS="${MODELS_DIR:-$HOME/models}"
BIN="${LLAMA_CPP:-$HOME/tools/llama.cpp}/build/bin/llama-quantize"
src="$MODELS/qwen3.5-4b-src/Qwen3.5-4B-BF16.gguf"
out="$MODELS/qwen3.5-4b-noimat"
mkdir -p "$out"
until [ -f "$src" ] && ! pgrep -f "hf download" >/dev/null; do sleep 20; done
for q in Q4_K_M Q3_K_M; do
  [ -f "$out/Qwen3.5-4B-$q-noimat.gguf" ] || "$BIN" "$src" "$out/Qwen3.5-4B-$q-noimat.gguf" "$q"
done
sha256sum "$out"/*.gguf
