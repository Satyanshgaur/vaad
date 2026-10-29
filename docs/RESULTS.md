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

## R6b. Paired language gaps from existing runs (2026-10-30, exploratory)

`python -m harness.compare <results.jsonl ...>`: pass^4 difference (second language minus
English) on **matched** `pair_id`s, bootstrap CI over tasks. Raw G0 runs use the original dev
set, so BFCL-Hinglish has only **18** matched pairs there; the gateway run uses the current dev
set (57 pairs). This is exploratory; the pre-registered version (H1) uses raw runs on the
current dev set (see PREREG.md and R8).

| Run | BFCL Hinglish - En | BFCL Hindi - En | Value-heavy Hinglish - En | Value-heavy Hindi - En |
|---|---|---|---|---|
| Qwen3.5-4B Q4_K_M raw (G0) | -22.2 [-44.4, 0.0] (18) | -35.5 [-48.4, -22.6] (62) | -65.2 [-82.6, -43.5] (23) | -43.5 [-65.2, -26.1] (23) |
| Qwen3.5-4B Q8_0 raw (G0) | -5.6 [-27.8, +16.7] (18) | -37.1 [-50.0, -24.2] (62) | -60.9 [-78.3, -39.1] (23) | -47.8 [-69.6, -26.1] (23) |
| Llama-3.2-3B Q4_K_M raw (G0) | -5.6 [-22.2, +11.1] (18) | -21.0 [-32.3, -9.7] (62) | -17.4 [-34.8, -4.3] (23) | -4.3 [-21.7, +8.7] (23) |
| Llama-3.2-3B Q8_0 raw (G0) | 0.0 [-16.7, +16.7] (18) | -17.7 [-29.0, -8.1] (62) | -13.0 [-26.1, 0.0] (23) | -13.0 [-26.1, 0.0] (23) |
| Qwen3.5-4B Q4_K_M, **gateway on, strict** (G1, current dev) | **-12.3 [-22.8, -1.8] (57)** | -33.9 [-46.8, -21.0] (62) | -65.2 [-82.6, -43.5] (23) | -43.5 [-65.2, -26.1] (23) |

(Values in points of pass^4; the matched-pair count is in parentheses.) Findings:
- On the 18-pair G0 sets every BFCL Hinglish-vs-English interval includes 0 (Qwen Q4 touches
  it), so those runs cannot decide the consistency question. The only 57-pair run excludes 0
  but is one model with the gateway on.
- Per-trial accuracy (pass@1) on Hinglish BFCL is near English (0.79 vs 0.80), yet pass^4
  differs by 12 points: the Hinglish deficit is **inconsistency across seeds**, not a lower
  per-try success rate. An earlier statement of "near parity" referred to pass@1 only.
- Value-heavy gaps are large and clear for Qwen at both precisions and smaller for Llama.
- The BFCL Hindi gap is large for every model, but see R6c: much of it is the answer key.

## R6c. Where the Hindi "wrong values" come from (2026-10-30, exploratory)

Qwen3.5-4B Q4_K_M, gateway on, current dev, BFCL-Hi. Of 83 single-call string mismatches, 44
had a Devanagari prediction; **43 of those are free-text fields** (`content`, `Title`,
`MetaDescription`, `keyword`, `query`, `new_alarm_name`...), one is an actor name (`starring`).
None are enums or ids. The model kept the user's language in free text while the BFCL-Hi answer
key kept English. One genuine error: a Devanagari URL slug (`UrlName`). So the BFCL Hindi gap
mixes real failures with an answer-key artifact; field-aware rescoring (H2) quantifies it.

Failure mix, Hinglish: wrong-value 65-70% of failures, wrong tool or missing arg 26-31%,
schema-invalid 5%. Among wrong-value arguments in Hinglish: 43 numbers, 10 times, 4 dates,
14 strings, 11 other.

Only 16 of the 57 dev BFCL-Hinglish tasks need a number, date or time value, and at most 8 of
those use a spoken form: BFCL-Hinglish barely tests normalization. Value-heavy is the only set
that does, and it was written adversarially (traps by design).

## R6d. First look at field-aware rescoring (2026-10-30, exploratory, unaudited)

`harness/rescore.py` with the pre-registered rules, bge-m3 embeddings, tau = 0.80 (the
provisional value; the audit has not been done, so nothing here supports a claim). Applied to
the Qwen3.5-4B Q4_K_M gateway run (`g1-strict`).

- **50 of 1,000 trials changed** from wrong to right.
- BFCL Hindi minus English: **-33.9 -> -32.3** points. BFCL Hinglish minus English: -12.3 ->
  -15.8 (English gained a little too, since rescoring applies to every language). Value-heavy:
  unchanged.
- **Correction to R6c / earlier discussion:** the Devanagari free-text mismatches are real but
  concentrated in about 7 of the 62 Hindi dev tasks (todo content, titles, alarm label, search
  queries, news keyword), and several of those tasks also fail on other arguments. The answer-key
  artifact explains **roughly a tenth of the Hindi gap, not most of it.** An earlier statement
  that the gap was "mostly a scoring artifact" was wrong.
- What the rest of the Hindi errors are (seed 0, single-call tasks): free text 12, identifier
  11 (a Devanagari URL slug, a Devanagari track name inside a `track:... artist:...` query, a
  wrong command, rating 5 vs 4.0, dict-shaped params), names 5 (`Rutherford, NJ` vs `Rutherford`,
  a near-miss actor name, missing state). Not all of these are Hindi-specific.
- **Classifier limit (pre-registered, so not changed after seeing this):** arrays of user
  utterances with names like `faq_describe_telephone_banking_start` are classified as
  identifiers, so a Hindi list where English was expected still scores wrong. The rules default
  unplaceable fields to exact, so rescoring here *under*-counts the artifact. A looser classifier
  can be reported as a clearly labelled exploratory variant, or added by a dated amendment.

## R7. G1 grammar ablation: strict vs loose date grammar (2026-10-30)

Qwen3.5-4B Q4_K_M through the gateway (schema tightening, validation, one retry) on the
**current 250-task dev set**, 4 seeds, temperature 0.7, thinking off. Reports:
`harness/reports/g1-strict`, `g1-loose` (results, summary, gateway trace). The loose run was
interrupted twice by out-of-memory kills of llama-server and finished with `--resume`; one
in-flight request appears twice in its gateway trace (1001 lines).

| Language (tasks) | Grammar | pass@1 | pass^4 | Schema-valid | Wrong-value | Flag rate |
|---|---|---|---|---|---|---|
| English (85) | strict | 0.829 | 0.788 [0.69, 0.87] | 100% | 9.1% | 1.2% |
| English (85) | loose | 0.826 | 0.788 [0.69, 0.87] | 100% | 9.1% | 1.2% |
| Hindi (85) | strict | 0.500 | 0.424 [0.32, 0.53] | 100% | 33.8% | 2.4% |
| Hindi (85) | loose | 0.491 | 0.388 [0.28, 0.49] | 100% | 34.4% | 2.4% |
| Hinglish (80) | strict | 0.631 | 0.525 [0.41, 0.64] | 100% | 25.9% | 1.3% |
| Hinglish (80) | loose | 0.641 | 0.550 [0.44, 0.66] | 100% | 25.6% | 1.3% |

- **Strict vs loose: no detectable difference.** Paired loose-minus-strict pass^4: English 0.0
  [0.0, 0.0], Hindi -3.5 [-8.2, 0.0], Hinglish +2.5 [-2.5, +7.5]. The default stays `strict`
  because nothing favours loose. The predicted "strict grammar forces a confident wrong date"
  effect is not visible at this size, probably because few tasks have a date to get wrong
  (most Hinglish wrong values are numbers and times, R6c).
- **Schema validity is 100%** in both (a flagged reply counts as valid; flags are 1-2%), above
  the 99% G1 target. The G0 raw runs were about 95% (old dev set).
- **Retries:** per 1,000 requests, 32-35 were retried; 16 recovered and 16 ended as flags in
  both runs; 115-116 were plain text answers with no call.
- **No accuracy gain is claimed.** The raw baseline on this dev set is R8 (next); G0 numbers
  were on the 211-task dev set and cannot be compared. The wrong-value rate (26-34% for
  Hindi/Hinglish) is untouched by grammar and repair, as expected: the grammar makes values
  well-formed, not right.
- **G1 exit:** schema-valid >= 99% (met, 100%); passthrough identical to the raw backend (met,
  gate 7 tests); the CI gates that exist at this phase (1, 2, 3, 7, 9, 10, split lock) run on
  every PR (gates 4, 5, 6 and 8 belong to Phase 2).

## R8. Raw baselines on the current dev set, and the model comparison  *in progress*

Raw condition (no gateway, no system prompt), Q4_K_M, current 250-task dev set, 4 seeds,
temperature 0.7, thinking off for Qwen. Reports `harness/reports/f1-<model>-Q4_K_M/raw`.
Decision rules: PREREG.md. Finished so far: Qwen3.5-4B, Granite-4.0-micro. Still running or
queued: Phi-4-mini, Llama-3.2-3B, the no-imatrix Q4_K_M and Q3_K_M, Qwen3.5-0.8B.

Per set, never pooled (pass^4 in points, mean [95% CI over tasks]; `python -m harness.breakdown`):

| Set | Language | Tasks | Qwen3.5-4B | Granite-4.0-micro |
|---|---|---|---|---|
| BFCL | English | 62 | 80.6 [71.0, 90.3] | 66.1 [54.8, 77.4] |
| BFCL | Hindi | 62 | 43.5 [30.6, 56.5] | 48.4 [35.5, 61.3] |
| BFCL | Hinglish | 57 | 71.9 [59.6, 82.5] | 63.2 [50.9, 75.4] |
| value-heavy | English | 23 | 87.0 [73.9, 100.0] | 82.6 [65.2, 95.7] |
| value-heavy | Hindi | 23 | 43.5 [21.7, 65.2] | 43.5 [26.1, 65.2] |
| value-heavy | Hinglish | 23 | 21.7 [4.3, 39.1] | 21.7 [4.3, 39.1] |

Per language over both sets (the pre-registered unit is the set; this is only for comparison
with G0): Qwen English 0.824, Hindi 0.435, Hinglish 0.575; Granite 0.706, 0.471, 0.512. Schema-valid
96.8/95.3/97.5% (Qwen) and 98.8/96.8/98.1% (Granite); wrong-value 7.6/33.2/23.7% and
14.4/35.3/30.9%; p50 latency 1.3 s (Qwen) and 0.6 s (Granite).

Qwen3.5-4B's English and Hindi numbers equal the G0 values (same tasks); Hinglish rose from
0.341 to 0.575 only because the Hinglish dev set grew from 41 to 80 tasks and changed (R6b).

### Paired gaps (pass^4, second language minus English, matched `pair_id`s)

| Model | BFCL Hinglish - En (57) | BFCL Hindi - En (62) | Value-heavy Hinglish - En (23) | Value-heavy Hindi - En (23) |
|---|---|---|---|---|
| Qwen3.5-4B | -8.8 [-19.3, +1.8] | -37.1 [-51.6, -22.6] | **-65.2 [-82.6, -43.5]** | -43.5 [-65.2, -26.1] |
| Granite-4.0-micro | -5.3 [-17.5, +5.3] | -17.7 [-32.3, -3.2] | **-60.9 [-78.3, -39.1]** | -39.1 [-60.9, -17.4] |

English BFCL pass^4 (the qualifying floor, PREREG.md >= 0.40): Qwen 0.806, Granite 0.661; both qualify.

**Preliminary reading against the pre-registered rules (not final until Phi-4-mini and Llama are in):**
- **H1 (consistency gap on natural Hinglish BFCL):** both qualifying models so far have a CI
  that **includes 0**. The rule says "does not stand" once two qualifying models include 0
  (with at least three qualifying models). The earlier -12.3 [-22.8, -1.8] came from Qwen with
  the gateway on; with the gateway off it is -8.8 [-19.3, +1.8]. Whether the rule can be applied
  depends on a third model qualifying.
- **H1b (spoken-form value gap, value-heavy):** the CI excludes 0 for both models, by a wide
  margin (-61 to -65 points). This part stands so far.
- The Hindi BFCL gap differs a lot by model (-37 vs -18); its explanation is H2 (pending).

### R9. Hindi diagnostic, field-aware rescoring and the Qwen-vs-Granite comparison (2026-10-30, exploratory)

**Status: exploratory.** Rescoring uses the pre-registered rules with the provisional tau = 0.80
and **no human audit yet**, so by PREREG.md none of this supports a claim. Rule amendment A1
(transliteration across scripts only) was made before these numbers were used; earlier rescored
numbers that were looser on same-script names are superseded.

**1. Where the Hindi string mismatches come from** (BFCL-Hi, single-call tasks, all seeds,
classified by the field classes in `harness/rescore.py`):

| Kind | Qwen3.5-4B | Granite-4.0-micro |
|---|---|---|
| Devanagari kept, free text | 38 | 33 |
| Devanagari kept, identifier | 5 | 5 |
| Devanagari kept, name | 1 | 8 |
| other mismatch (Latin), identifier | 7 | 14 |
| other mismatch (Latin), name | 15 | 14 |
| other mismatch (Latin), free text | 0 | 3 |
| **total string mismatches** | 66 | 77 |
| **share: Devanagari kept in free text** | **58%** | **43%** |

Qwen's share is higher, but not clearly: 38/66 vs 33/77 gives chi-square 3.08 (below 3.84), and
trials of the same task are not independent, so the real uncertainty is larger. Qwen makes fewer
mismatches overall; Granite makes more Latin-script errors (identifiers 14, names 14).

**2. Field-aware rescored pass^4** (points; set never pooled):

| Set | Language | Qwen raw to rescored | Granite raw to rescored | Rescored minus raw (both models) |
|---|---|---|---|---|
| BFCL | English | 80.6 to 82.3 | 66.1 to 67.7 | +1.6 [0.0, +4.8] |
| BFCL | Hindi | 43.5 to 50.0 | 48.4 to 54.8 | **+6.5 [+1.6, +12.9]** |
| BFCL | Hinglish | 71.9 to 73.7 | 63.2 to 63.2 | +1.8 [0.0, +5.3] Qwen; 0.0 Granite |
| value-heavy | all three | unchanged | unchanged | 0.0 |

Rescoring moves 24 (Qwen) and 25 (Granite) of 1,000 trials. The Hindi BFCL gain is the same
+6.5 [+1.6, +12.9] for both models (the same 4 tasks flip).

**3. The Hindi-minus-English BFCL gap, raw vs rescored** (paired on the 62 matched pairs):

| Model | Raw | Rescored | Share of gap that remains |
|---|---|---|---|
| Qwen3.5-4B | -37.1 [-51.6, -22.6] | -32.3 [-45.2, -19.4] | 87% |
| Granite-4.0-micro | -17.7 [-32.3, -3.2] | -12.9 [-27.4, +1.6] | 73% |

Against H2: "largely a scoring artifact" needs <= 50% remaining on at least two qualifying models
(and a passed audit): **not met** (87% and 73%). "Persists" needs a CI excluding 0 and >= 10
points on two models: met for Qwen, not for Granite (its rescored CI includes 0). So: **partly
explained (about 13-27%), not largely**; undecided pending more models and the audit.

**4. Qwen minus Granite, paired on the same tasks** (points):

| Set | Language | Tasks | Raw | Rescored |
|---|---|---|---|---|
| BFCL | English | 62 | +14.5 [+3.2, +25.8] | +14.5 [+3.2, +25.8] |
| BFCL | Hindi | 62 | **-4.8 [-14.5, +4.8]** | **-4.8 [-14.5, +4.8]** |
| BFCL | Hinglish | 57 | +8.8 [-3.5, +21.1] | +10.5 [-1.8, +22.8] |
| value-heavy | English / Hindi / Hinglish | 23 | +4.3 / 0.0 / 0.0 (CIs +-9 to +-20) | same |

On Hindi, Granite is nominally ahead of Qwen (the reverse of English), but the interval
includes 0 and **rescoring does not change it**: the sign is the same and the CI still includes
zero. **No ranking flip on these two models** (H3 not met, and the audit is not done). Phi-4-mini
and Llama will show whether any ordering change appears.

### Gateway (grammar + retry) vs raw, Qwen3.5-4B, paired pass^4 (exploratory)

| Condition minus raw | English | Hindi | Hinglish |
|---|---|---|---|
| gateway, strict date grammar | -3.5 [-8.2, 0.0] | -1.2 [-5.9, +3.5] | -5.0 [-11.3, 0.0] |
| gateway, loose date grammar | -3.5 [-8.2, 0.0] | -4.7 [-10.6, 0.0] | -2.5 [-10.0, +3.7] |

**Schema tightening, validation and one retry do not improve accuracy; the point estimates are
slightly negative in every cell** (all intervals touch 0). They raise schema validity (about 96%
to 100%) without fixing wrong values, and may cost a few points. This is the "grammar
constraints hurt" risk in the brief's risk table. Possible causes (untested): the `maxLength`
cap and inferred enums constraining generation, and the retry note sometimes steering the model
away from a correct first call. The right response is to isolate the pieces in the Phase 2
ablations, not to claim a gain from grammar.
