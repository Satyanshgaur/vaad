#!/usr/bin/env bash
# H8 (docs/PREREG.md, amendment A3): calibration versus tensor allocation, Qwen3.5-4B Q4_K_M.
# All arms are built from the BF16 GGUF at one llama.cpp commit:
#   A0 default allocation, no imatrix                (exists: qwen3.5-4b-noimat)
#   A1 default allocation + English imatrix          A2 default allocation + Indic imatrix
#   A3 unsloth's tensor allocation, no imatrix       (scripts/unsloth_q4km_tensor_types.txt)
# Needs data/calibration/calibration_{en,indic}.txt (scripts/make_calibration.py), then evaluates
# each new arm on the full dev set.
set -euo pipefail
source "$(dirname "$0")/lib_resilient.sh"
BIN="${LLAMA_CPP:-$HOME/tools/llama.cpp}/build/bin"
SRC="$HOME/models/qwen3.5-4b-src/Qwen3.5-4B-BF16.gguf"
OUT="$HOME/models/qwen3.5-4b-h8"
mkdir -p "$OUT"
for corpus in en indic; do
  [ -f "$OUT/imat_$corpus.gguf" ] || "$BIN/llama-imatrix" -m "$SRC" -f "data/calibration/calibration_$corpus.txt" \
      -o "$OUT/imat_$corpus.gguf" --chunks 80 -c 512 -ngl 14 --no-ppl
done
[ -f "$OUT/A1-en.gguf" ]    || "$BIN/llama-quantize" --imatrix "$OUT/imat_en.gguf" "$SRC" "$OUT/A1-en.gguf" Q4_K_M
[ -f "$OUT/A2-indic.gguf" ] || "$BIN/llama-quantize" --imatrix "$OUT/imat_indic.gguf" "$SRC" "$OUT/A2-indic.gguf" Q4_K_M
[ -f "$OUT/A3-alloc.gguf" ] || "$BIN/llama-quantize" --tensor-type-file scripts/unsloth_q4km_tensor_types.txt "$SRC" "$OUT/A3-alloc.gguf" Q4_K_M
sha256sum "$OUT"/*.gguf
for arm in A1-en A2-indic A3-alloc; do
  scripts/run_one.sh "qwen3.5-4b-h8-$arm" Q4_K_M "$OUT/$arm.gguf" --no-think
done
