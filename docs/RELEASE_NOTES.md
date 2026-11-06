# vaad 1.0.0

A deterministic Hindi/Hinglish spoken-value layer for small local models, as a Python library, a CLI and an
OpenAI-compatible gateway. **Text only.** Audio is v2.

## What it does

- Parses spoken-form numbers ("dedh hazaar" = 1500), money (lakh, crore), quantities, clock times
  ("saade aath baje"), durations, phone numbers and relative dates, with a span, a calibrated confidence and a
  reason. When the text is ambiguous (AM or PM, an unmarked "kal") it asks instead of guessing.
- `annotate_turn(text, ref_date)` writes the parsed value after each span; the gateway can also verify the
  arguments of a model's tool call (`canon.mode`: off, annotate, verify, both).
- CLI: `vaad parse "<text>"`, `vaad gaps FILE.csv` (lexicon gaps from private text, counts only),
  `vaad serve` (gateway). Audit trail per argument in the gateway trace (offsets only, phones masked).

## Measured (see docs/RESULTS.md, docs/CALIBRATION.md; caveats there)

- Held-out human-typed tool-calling tasks (189, three small models): pass^4 +16 to +22 points with the
  normalizer, wrong values 23-42% to 7-9% when it may ask.
- Outputs the parser was at least 90% sure of were right 97-100% of the time on held-out data.
- Pre-registered test-split run: on the untouched test split the normalizer raised value-heavy pass^4
  by +16 to +44 points on all three models (CIs above 0; value-heavy Hinglish +37 to +59 with `both`). Two
  pre-registered targets were **not** met: English accuracy may drop by up to a few points (CI lower bounds -7 to
  -13), and pooled Hinglish gain for Qwen was +7.3 [-1.8, +15.5] against the +10 target. See RESULTS R21.

## Known limits (read these)

- **Text only.** Behaviour on ASR output is untested.
- **Lexicons are AI-written and not yet reviewed by a native speaker** (a review sheet is prepared).
- Three small models (3-4B), one hardware setup, one reference date in the experiments.
- Test tasks were written to contain values; real chat rarely does (spoken-form numbers: 0.4% of real
  messages). The gain applies where messages carry values: orders, payments, reminders, voice agents.
- `canon.mode: both` costs English accuracy on the development set; `annotate` is the safe default.

## Install

```sh
pip install vaad-1.0.0-py3-none-any.whl     # from the release assets
vaad parse "kal saade aath baje dedh hazaar rupaye" --ref-date 2026-11-05
```

Apache-2.0.
