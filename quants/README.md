# Indic quants (Phase 3)

Planned contents:

- `calibration/` — Hindi and Hinglish calibration text (licensed sources only; list them here).
- `build.sh` — `llama-imatrix` on the calibration text, then `llama-quantize` to Q4_K_M,
  producing a standard-calibrated and an Indic-calibrated quant per model.
- `card.py` — runs the harness on both quants and writes a reliability card for the
  Hugging Face model page (numbers, test-split hash, harness version).

Check each base model's licence allows redistributing quants before uploading.
