#!/usr/bin/env bash
# G0 baseline on the dev split: raw model twice (reproducibility) + strong system prompt.
# Expects llama-server on $URL serving the model named by $MODEL/$QUANT.
set -euo pipefail
URL="${URL:-http://127.0.0.1:8080}"; MODEL="${MODEL:-qwen3.5-4b}"; QUANT="${QUANT:-Q4_K_M}"
OUT="harness/reports/g0-${MODEL}-${QUANT}"
common=(--tasks harness/tasks/dev --base-url "$URL" --model "$MODEL" --quant "$QUANT" --no-think)
uv run python -m harness.run "${common[@]}" --out "$OUT/raw-a"
uv run python -m harness.run "${common[@]}" --out "$OUT/raw-b"
uv run python -m harness.run "${common[@]}" --system-prompt harness/prompts/strong_system.txt --out "$OUT/prompt"
