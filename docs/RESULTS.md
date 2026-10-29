# Results log

Every measured number in one place, with where it came from. Add a section for each new run;
never edit an old one. See METHODS.md for what each metric means and DATA.md for the dev set.

**Caveat that applies to everything here:** these are all **dev-split** numbers. The test
split has not been run (it runs once, at Phase 4).

Setup for all runs unless stated: llama.cpp commit `df9beac` (CUDA, sm_86), RTX 3050 6 GB
laptop GPU, `--jinja`, all layers on GPU, context 8192, temperature 0.7, seeds 0-3, thinking
off for Qwen3.5, `max_tokens` 512. Model files and hashes: `harness/models.yaml`.

## R1. G0 baseline: the language gap (2026-10-24)

Qwen3.5-4B Q4_K_M, raw, dev (**the original 211-task dev set**: English 85, Hindi 85, Hinglish 41).
Report: `harness/reports/g0-qwen3.5-4b-Q4_K_M/raw-a` (a second identical run `raw-b`).

| Language (tasks) | pass@1 | pass^4 | Schema-valid | Wrong-value | p50 / p95 latency |
|---|---|---|---|---|---|
| English (85) | 0.856 [0.78, 0.92] | 0.824 [0.74, 0.89] | 96.8% | 7.6% | 1.3 s / 3.5 s |
| Hindi (85) | 0.512 [0.41, 0.61] | 0.447 [0.34, 0.55] | 95.3% | 33.2% | 1.3 s / 8.3 s |
| Hinglish (41) | 0.463 [0.33, 0.60] | 0.341 [0.20, 0.49] | 95.1% | 34.8% | 1.4 s / 4.6 s |

- Re-running seeds 0-3 gives identical numbers (deterministic per seed). A fresh run with seeds
  4-7 (`raw-seeds4-7`) stays inside every interval: pass^4 moves by at most 2.4 points,
  Hinglish wrong-value by 6.1 points.
- **Headline:** English 0.82 vs Hinglish 0.34 pass^4, and about a third of Hindi and Hinglish
  calls execute with a wrong value. Schema validity is about 95% in every language, so the
  failures are in *values*, not format.
- Failure examples: "paanch sau" gave 50,000 rupees; "dedh crore" gave 8 crore; "saade nau
  baje" gave 21:00; "parson" gave today; a transfer executed to a 9-digit phone number.

## R2. Strong-system-prompt baseline (2026-10-24)

Same model and dev set, with `harness/prompts/strong_system.txt` (report `.../prompt`).

| Language | Change in pass^4 vs raw (paired 95% CI) | Wrong-value |
|---|---|---|
| Hinglish | **+12.2 points** [+0.0, +26.8] | 32.3% (raw 34.8%) |
| English | **-5.9 points** [-11.8, -1.2] (a real loss) | n/a |
| Hindi | no change | n/a |

Prompting alone is not a free fix: it helps Hinglish a little and hurts English. Best
baseline for the launch target: Hinglish prompt (0.463), English raw (0.824).

## R3. G0 grid: compression, claim C1 (2026-10-24 to 25)

pass^4, raw model, dev (original 211 tasks), 4 seeds. Change = 4-bit minus 8-bit, paired 95% CI.
Reports: `harness/reports/g0-{qwen3.5-4b,llama3.2-3b}-{Q8_0,Q4_K_M}/raw-a`.

| Model | Language | Q8_0 | Q4_K_M | Change | Schema-valid (Q8 to Q4) | Wrong-value (Q8 to Q4) |
|---|---|---|---|---|---|---|
| Qwen3.5-4B | English | 0.776 | 0.824 | +4.7 [0.0, +10.6] | 97% to 97% | 7.9% to 7.6% |
| Qwen3.5-4B | Hindi | 0.376 | 0.447 | **+7.1 [+1.2, +14.1]** | 96% to 95% | 31.8% to 33.2% |
| Qwen3.5-4B | Hinglish | 0.390 | 0.341 | -4.9 [-17.1, +7.3] | 95% to 95% | 37.8% to 34.8% |
| Llama-3.2-3B | English | 0.259 | 0.294 | +3.5 [-1.2, +9.4] | 42% to 46% | 10.0% to 8.5% |
| Llama-3.2-3B | Hindi | 0.094 | 0.129 | +3.5 [-2.4, +9.4] | 40% to 44% | 21.2% to 20.3% |
| Llama-3.2-3B | Hinglish | 0.146 | 0.146 | 0.0 [0.0, 0.0] | 32% to 31% | 17.7% to 15.9% |

- **C1 (compression hurts Hindi/Hinglish more than English) is not supported at this scale.**
  Going from 8-bit to 4-bit never hurts Hindi or Hinglish more than English; the only change
  whose interval excludes zero is a Hindi *gain* for Qwen. Possible cause, untested: the
  unsloth imatrix calibration used for that 4-bit file.
- Llama-3.2-3B often breaks the tool-call format: only 31-46% of its calls are schema-valid;
  numbers arrive as strings (`"weight_kg": "1"`); 7-15% of trials are output llama-server cannot
  parse. Its low wrong-value rate is a side effect (calls fail schema validation first).
- Consequence for the paper: lead with the **language gap and wrong-value execution**, which
  hold at both precisions; C1 becomes an analysis. Phase 3's controlled standard-vs-Indic
  imatrix quants should test the calibration question properly.

## R4. Cost and timing (2026-10-24)

Qwen3.5-4B Q4_K_M, 211 dev tasks, thinking off: **2.69 s mean, 1.81 s p50, 7.3 s p95** per call.
With thinking on: about 7.9 s per call. Launch grid: about 24,000 calls x 2.69 s, about 18 GPU
hours. Report: `harness/reports/w1-timing-qwen4b-q4`.

## R5. Gate 9 smoke baseline (2026-10-29)

Qwen3.5-0.8B Q8_0, CPU, 50 dev tasks (spread over every source and language), temperature 0.
Local: schema-valid **0.98**, correct 0.54 (`harness/reports/smoke_baseline.json`). GitHub
Actions runner: schema-valid 0.98, correct 0.56; the whole job took 4.2 minutes on PR 5 and
5.6 minutes on PR 6. The gate fails below 0.88.

## R6. Proxy checks (2026-10-29)

- Real 0.8B llama-server through the gateway: a Hinglish weather request returns the right
  call; one trace line with backend time 750 ms; `/v1/models` relayed.
- Strict date grammar accepted by llama-server and produces well-formed ISO dates; one
  observed confident-wrong date ("kal" with today = 2026-10-24 gave 2026-10-24).

## R7. G1 grammar ablation (strict vs loose date grammar)  *pending*

Run: `scripts/grammar_ablation.sh strict loose` (Qwen3.5-4B Q4_K_M through the gateway, **current
250-task dev set**, 4 seeds). Reports: `harness/reports/g1-strict`, `g1-loose`. These are not
comparable to R1 until the raw baseline is re-run on the current dev set. To fill in:

| Condition | Language | pass^4 | Schema-valid | Wrong-value | Flag rate |
|---|---|---|---|---|---|
| raw (current dev) | | | | | |
| grammar-strict | | | | | |
| grammar-loose | | | | | |

G1 exit: schema-valid at least 99% with grammar on; passthrough identical to raw (tested by
gate 7); gates 1-9 live in CI.
