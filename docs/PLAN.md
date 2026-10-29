# vaad: execution plan

This is the working plan, built from [brief.md](brief.md). The brief explains the *why*. This
file lists *what to do each week* and *how each gate is checked*. Tick boxes as work lands, and
add measured numbers (timings, baseline, launch target) where marked.

Budget: about 8 weeks part-time, about 130 hours. A missed gate moves every later date. It is
never skipped.

## Standing rules

1. Tune lexicons, prompts and router thresholds on the **dev** split only.
2. Run the **test** split once per release, and never to chase a number.
3. Run 4 seeds per task per condition at temperature 0.7, plus a temperature-0 pass@1 check.
4. Report bootstrap 95% intervals. A gain counts only when the **paired** bootstrap 95%
   interval of the per-task difference excludes 0 (`harness.metrics.paired_bootstrap_ci`;
   both conditions run on the same tasks). Decided at G0 in place of the brief's
   non-overlap rule, which on 41 Hinglish dev tasks would need a gain of about 30 points.
5. Freeze model file hashes, quant files and prompts in every results file.
6. The out-of-scope table in the brief is the contract. New ideas go into GitHub issues
   labelled `v2`.
7. One change per PR, with a conventional-commit title. Use the PR template.

## Launch target (written at G0 on 2026-10-24, then never moved)

Model: Qwen3.5-4B Q4_K_M. The target is checked **once, on the test split**, at Phase 4.
"Best baseline" means the better of the raw model and the strong system prompt, per language.
The test baselines are measured in that same Phase 4 run.

| Metric | Baseline (dev, seeds 0–3) | Target (test) |
|---|---|---|
| Hinglish pass^4, gateway on vs best baseline | raw 0.341, prompt **0.463** | ≥ best baseline **+ 10 pts**, paired 95% CI of the gain > 0 |
| English pass^4, gateway on vs raw | raw **0.824**, prompt 0.765 | paired 95% CI lower bound of the change ≥ −3 pts |
| Hinglish wrong-value execution rate | raw **34.8%**, prompt 32.3% | below raw, paired 95% CI of the change < 0 |
| Added p50 latency, canonicalizer only | n/a | < 20 ms |

### G0 baseline (dev, Qwen3.5-4B Q4_K_M, 4 seeds, temperature 0.7)

| Language (tasks) | pass@1 | pass^4 | Schema-valid | Wrong-value | p50 / p95 latency |
|---|---|---|---|---|---|
| English (85) | 0.856 [0.78, 0.92] | 0.824 [0.74, 0.89] | 96.8% | 7.6% | 1.3 s / 3.5 s |
| Hindi (85) | 0.512 [0.41, 0.61] | 0.447 [0.34, 0.55] | 95.3% | 33.2% | 1.3 s / 8.3 s |
| Hinglish (41) | 0.463 [0.33, 0.60] | 0.341 [0.20, 0.49] | 95.1% | 34.8% | 1.4 s / 4.6 s |

- **Reproducibility:** re-running seeds 0–3 gives identical numbers (llama-server is
  deterministic per seed). A fresh run with seeds 4–7 stays inside every interval: pass^4
  moves by at most 2.4 points, and Hinglish wrong-value by 6.1 points.
- **Strong prompt:** Hinglish pass^4 +12.2 points (paired CI [+0.0, +26.8]), English −5.9
  points (paired CI [−11.8, −1.2]: a real loss), Hindi no change. So prompting alone is not a
  free fix.
- **The failures are the target problem:** "paanch sau" → ₹50,000, "dedh crore" → 8 crore,
  "saade nau baje" → 21:00, "parson" → today, and a transfer executed to a 9-digit phone.
- Reports: `harness/reports/g0-qwen3.5-4b-Q4_K_M/` (`raw-a`, `raw-b`, `raw-seeds4-7`, `prompt`).

### G0 grid: compression (claim C1), raw model, dev, seeds 0–3

pass^4 per language. The change is 4-bit minus 8-bit, with a paired 95% CI.

| Model | Language | Q8_0 | Q4_K_M | Change | Schema-valid (Q8→Q4) | Wrong-value (Q8→Q4) |
|---|---|---|---|---|---|---|
| Qwen3.5-4B | English | 0.776 | 0.824 | +4.7 [0.0, +10.6] | 97% → 97% | 7.9% → 7.6% |
| Qwen3.5-4B | Hindi | 0.376 | 0.447 | **+7.1 [+1.2, +14.1]** | 96% → 95% | 31.8% → 33.2% |
| Qwen3.5-4B | Hinglish | 0.390 | 0.341 | −4.9 [−17.1, +7.3] | 95% → 95% | 37.8% → 34.8% |
| Llama-3.2-3B | English | 0.259 | 0.294 | +3.5 [−1.2, +9.4] | 42% → 46% | 10.0% → 8.5% |
| Llama-3.2-3B | Hindi | 0.094 | 0.129 | +3.5 [−2.4, +9.4] | 40% → 44% | 21.2% → 20.3% |
| Llama-3.2-3B | Hinglish | 0.146 | 0.146 | 0.0 [0.0, 0.0] | 32% → 31% | 17.7% → 15.9% |

- **C1 is not supported at this scale.** Going from 8-bit to 4-bit never hurts Hindi or
  Hinglish more than English. The only change whose CI excludes zero is a Hindi *gain* for
  Qwen. A possible cause is the unsloth imatrix used for that 4-bit file (untested). Per the
  brief's fallback, the paper leads with the **language gap and wrong-value execution**, which
  hold at both precisions. C1 becomes an analysis ("compression is not the problem here"), and
  Phase 3's controlled std-vs-Indic imatrix quants should test it properly.
- **Llama-3.2-3B often breaks the tool-call format.** Only 31–46% of its calls are
  schema-valid. Numbers come back as strings (`"weight_kg": "1"`), and 7–15% of trials are
  output llama-server cannot parse (scored as failed trials, `error` field). Its low
  wrong-value rate is a side effect: most calls fail schema validation before a value can be
  wrong. This makes Llama the stronger test case for Phase 1's grammar layer.
- Reports: `harness/reports/g0-{qwen3.5-4b,llama3.2-3b}-{Q8_0,Q4_K_M}/raw-a`
  (`scripts/baseline_grid.sh`).

Measured seconds per call: **2.69 s mean, 1.81 s p50, 7.3 s p95** (Qwen3.5-4B Q4_K_M, RTX 3050
6 GB, thinking off, 211 dev tasks, 2026-10-24). With thinking on, a call takes ~7.9 s, so the
grid runs with thinking off. Launch grid budget: ~24k calls × 2.69 s ≈ **18 GPU-hours**. The
brief assumed 3 s/call, ~24k calls and ~20 h. This is under the 6 s fallback threshold.

---

## Phase 0: Setup and baseline (Week 1, ~18 h) → G0

**Repo and CI** (done in the initial scaffold)
- [x] uv project, src layout, ruff, mypy, pytest config
- [x] Typed stage interfaces: `server/`, `router/`, `grammar/`, `canon/`
- [x] Harness core: `schema.py`, `metrics.py`, `split.py`, `score.py`, `leakage.py`
- [x] CI gates 1, 2, 3 and 10, plus the split-lock check
- [x] Push the branch, open the first PR, confirm CI is green on GitHub (PR #1, merged)

**Backend**
- [x] Build llama.cpp with CUDA in `~/tools/llama.cpp` (commit df9beac, `-DCMAKE_CUDA_ARCHITECTURES=86`)
- [x] Shortlist: **Qwen3.5-4B** (primary) and **Llama-3.2-3B** (second family), each at Q8_0
      and Q4_K_M, plus **Qwen3.5-0.8B** Q8_0 for the CI smoke gate. Files in `~/models/`
- [x] Qwen3.5-4B emits native tool calls via `scripts/llama_server.sh` (`--jinja`)
- [x] Llama-3.2-3B emits native tool calls (but often malformed; see the G0 grid)
- [x] Qwen3.5-0.8B Q8_0 emits native tool calls too (English and Hinglish weather query, valid JSON args)
- [x] Record the GGUF files and SHA256 hashes in `harness/models.yaml`
- [x] Time one call and fill in the budget above (2.69 s: no fallback needed)

**Task sets** (format: `harness.schema.Task`, one JSON line per task)
- [x] `bfcl_hi`: `harness/importers/bfcl.py` reads the BFCL-Hi JSON directly. 150 tasks
      (60 simple, 50 multiple, 7 parallel, 8 parallel_multiple, 25 irrelevance)
- [x] `bfcl_en`: paired Gorilla BFCL v4 live originals. Licence is **Apache-2.0**. Both
      languages use BFCL-Hi's (v2) functions and answers; pairs whose answer changed in v4
      are dropped
- [x] `bfcl_hinglish`: first 89 rewrites (AI-drafted, then reviewed by a native Hindi speaker
      and an AI pass, 2026-10-29; 9 fixes applied)
- [x] Hinglish grown to 140 rewrites (57 dev, 83 test). The last 51, all in test, were drafted
      by Claude on 2026-10-29 and had only an AI pass, so they are marked `native_checked: false`
      (CSV for reviewers: `private/review/hinglish_rewrites_batch3.csv`). 4 test tasks with
      non-English originals (Korean, Thai, Chinese, one meta-prompt) have no Hinglish version,
      so 150 is not reached.
- [x] `value_heavy`: 50 scenarios × 3 languages, 11 tools, including 3 `clarify` scenarios
      where asking back is the only correct answer (AI-drafted, then native-reviewed by a Hindi speaker, 2026-10-29; 11 fixes applied, "kal" trap in statement-01 kept)
- [x] Splits frozen in `harness/tasks/SPLITS.lock`: 211 dev / 286 test tasks at G0, re-locked on
      2026-10-29 to **250 dev / 338 test** after the Hinglish growth and the native-review fixes
      (one BFCL pair dropped from test because its question repeats a dev task). The G0
      baseline numbers below are on the original 211-task dev set (see docs/DATA.md). Rebuilding from
      pinned upstream revisions reproduces them byte-for-byte (`harness/tasks/README.md`)
- [x] Test-split policy: **hashed-private**. Test tasks and their sources live in the private
      repo `Satyanshgaur/vaad-private` (`scripts/private_sync.sh`). Only hashes are public:
      `SPLITS.lock`, plus `test_ngrams.txt` so gate 10 runs in CI without the text

**Harness**
- [x] `run.run_trial`: call the backend, parse `tool_calls`, score with `score.calls_match`
- [x] Wrong-value detection: right functions, schema-valid arguments, but the call is incorrect
- [x] Report writer: `harness/reports/<run>/results.jsonl`, `summary.json`, JSONL traces
- [x] Summary: pass@1, pass^4, schema-valid, wrong-value, p50/p95 latency, with 95% CIs, by
      language (flag rate arrives with the gateway)

**Baseline**
- [x] Raw model on dev, 4 seeds, run **twice**, plus a seeds 4–7 run (`scripts/baseline_g0.sh`)
- [x] Strong-prompt baseline (`harness/prompts/strong_system.txt`)
- [x] Fill in the launch target table above
- [x] Same baseline for Llama-3.2-3B and for both Q8_0 quants (C1 not supported; see above)
- [x] Grow Hinglish dev past 41 tasks before G2: now 80 Hinglish dev tasks (57 BFCL + 23 value-heavy).
      The G0 raw baseline must be re-run on the current dev set before comparing to it

**G0 passed on 2026-10-24** (Qwen3.5-4B Q4_K_M): runs reproduce, splits are locked, and the
target is written down.

**G0 exit:** the two raw runs agree within their intervals, `SPLITS.lock` is committed, and
the launch target is written down.
**Fallback:** if Hinglish pass^4 is already close to English, move the claim to smaller or
4-bit models, or lead with the wrong-value execution rate.

## Phase 1: Proxy, grammar, CI (Weeks 2–3, ~30 h) → G1

**Week 2: proxy**
- [x] `server/backend.py`: httpx `AsyncClient` per backend, with timeouts and error mapping
- [x] `server/routes.py`: `/v1/chat/completions` (non-streaming, with tools) and `/v1/models`.
      `stream: true` is refused with 400 when the gateway is on and streams through when it is off
- [x] `gateway_enabled: false` gives a byte-faithful passthrough
- [x] One JSONL trace per request: lang, tier, raw args, canonical args, decision, ms per stage
      (lang, canonical args and decision stay empty until langid and the canonicalizer land)
- [x] Gate 7: contract tests in `tests/integration/` using a `respx`-mocked backend. Check the
      OpenAI response shape and that passthrough with the gateway off changes nothing
- [x] Gate 9: smoke eval on 50 dev tasks with the ~0.5B model on the CI CPU, 1 seed. Compare
      the schema-valid rate to the stored `harness/reports/smoke_baseline.json`
- [ ] Kaggle notebook (a): reproduce the baseline on free T4s

**Week 3: grammar and repair**
- [x] `grammar/tighten.py`: add `pattern`, `enum` and `maxLength`. Dates get an ISO pattern.
      Numbers stay numbers. Drop keywords llama.cpp does not support
- [x] `grammar/validate.py`: check again after generation (the jsonschema validator already exists)
- [x] Guided retry: one retry with the validator errors added to the prompt
- [x] Flag response: an assistant message carrying the clarification text plus a `vaad_flag`
      field, instead of a `tool_call`
- [x] Ablation switch: strict date grammar versus loose grammar plus canonicalization
      (`grammar.date_grammar` in the config; `scripts/grammar_ablation.sh` runs both on dev)

**G1 exit:** passthrough is identical to calling the raw backend, the schema-valid rate is at
least 99% with grammar on, and gates 1–9 run in CI.

**G1 passed on 2026-10-30** (schema-valid 100% on the current dev set, strict and loose; gate 7
passes; the gates that exist at this phase run in CI). No accuracy gain from grammar and retry
alone: see RESULTS R7. Strict stays the default.

## Phase 2: Canonicalizer (Weeks 4–5, ~35 h) → G2

**Week 4: numbers, money, units, phones**
- [ ] Lexicons (YAML, with provenance in each PR): number words in Hinglish and Devanagari,
      fractions (aadha, dedh, dhai, saade, sava, paune), lakh/crore, currency words, units
- [ ] `numbers.py`, `money.py`, `units.py`, `phones.py`. Every parser returns
      `Canonicalized(value, confidence, source span, reason)`
- [ ] Context handling for ambiguous words, e.g. "do" means *two* in "do kilo" but *give* in
      "bhej do"
- [ ] Use NeMo Hindi ITN as a reference or fallback for Devanagari spoken forms

**Week 5: dates, times, decisions**
- [ ] `dates.py`: aaj, kal, parson, narson, agle/pichhle + weekday, with `dateparser` as a fallback
- [ ] "kal" resolver: verb tense ("bhej do" or "karna hai" → future; "aaya tha" or "kiya tha" →
      past), then field meaning (e.g. `delivery_date` → future), otherwise **flag**
- [ ] `times.py`: subah, dopahar, shaam, raat with baje, saade, sava, paune
- [ ] `canonicalize()`: the schema chooses the value type. Free-text fields are never changed
- [ ] `decide.py` thresholds tuned on dev (the decision logic already exists)
- [ ] Gate 4: `tests/golden/canon_cases.yaml` with 300+ cases
- [ ] Gate 5: hypothesis tests for round trips, idempotence, and free text left untouched
- [ ] Gate 6: no value invention. Every output traces to a span in the user turn or to the
      reference date
- [ ] Gate 8: pytest-benchmark p95 under 20 ms for 1,000 calls, and no more than 25% slower than main
- [ ] Turn on coverage for `vaad.canon` (`--cov-fail-under=90`) in CI
- [ ] Literature check (brief, "Where to look") before making any novelty claims
- [ ] Draft the canonicalization gold set as a dataset with a datasheet

**G2 exit:** Hinglish dev pass^4 rises with intervals that do not overlap, English is no
worse, the wrong-value rate falls, and there are 300+ golden cases. Email the closest authors
once this passes.

## Phase 3: Router and quants (Week 6, ~17 h) → G3

- [ ] `router/langid.py`: Devanagari script ratio plus a Hinglish word-list score. Returns
      en, hi or hinglish with a confidence, in under 1 ms
- [ ] `router/difficulty.py`: number of tools offered, multi-call cues, numbers or dates in the turn
- [ ] `router/policy.py`: rules read from config, thresholds tuned on dev
- [ ] `quants/`: calibration text, `build.sh` (imatrix → Q4_K_M, standard versus Indic), `card.py`
- [ ] Kaggle notebook (c): build an Indic quant

**G3 exit:** the router beats both single tiers on accuracy per unit of latency on dev, and the
Indic-calibrated quant has been compared with the standard one on dev.

## Phase 4: Test run, docs, demo (Week 7, ~17 h) → G4

- [ ] The one test-split run: full grid, ablations (grammar only, canonicalizer only, router
      only) and baselines (raw, strong prompt, blind retry). Commit the CSV and traces
- [ ] README with the results table and a quickstart that takes under 5 minutes
- [ ] Dockerfile, a GHCR publish workflow and a PyPI publish workflow
- [ ] `examples/order_agent/`, plus the demo video
- [ ] Kaggle notebook (b): run the gateway on your own tools
- [ ] Draft the write-up

**G4 exit:** as defined in the brief.

## Phase 5: Launch (Week 8, ~13 h)

- [ ] arXiv preprint and blog post
- [ ] Hugging Face datasets with datasheets: BFCL-Hinglish, the value-heavy set, the gold set.
      Mirror them on Kaggle
- [ ] Hugging Face quants with reliability cards
- [ ] Zenodo DOI for the release
- [ ] Posts, emails to researchers, issue triage

---

## Follow-up experiments (pre-registered in PREREG.md, 2026-10-30)

Run in this order, on dev only, thresholds fixed beforehand:
- [x] Paired pass^4 English vs Hinglish on matched tasks (`harness/compare.py`): existing runs
      are inconclusive on 18 pairs; see RESULTS R6b
- [x] Raw dev runs on the current dev set: Qwen3.5-4B, Granite-4.0-micro, Phi-4-mini (0 tool
      calls: template mismatch), Llama-3.2-3B (below floor); third family Ministral-3-3B added
      by amendment A2 and queued. H1 inconclusive until it runs; H1b stands (RESULTS R10)
- [ ] Field-aware rescoring of BFCL-Hi (`harness/rescore.py`), human audit of about 50 cases
      (`private/review/rescore_audit.csv`), then H2 and H3
- [ ] Qwen3.5-4B Q4_K_M and Q3_K_M built without an imatrix (`scripts/make_quants.sh`), H4
- [ ] Qwen3.5-0.8B on the full dev set, H5 (descriptive)

Deferred to v2: multi-turn tasks; voice clips and real Hinglish requests (Sarvam/Gnani);
models above 4B; quants below Q3.

## Things only you can do

- [x] Build llama.cpp and download the candidate GGUFs
- [x] Find native Hindi speakers to check the task sets: two found (one per set, 2026-10-29).
      Still open: a reviewer for the 51 batch-3 test rewrites, and the lexicons (Phase 2)
- [x] Confirm the Gorilla BFCL licence (Apache-2.0) and each base model's licence for quants
- [ ] Choose the strong tier for the demo: a local 8-bit model on Kaggle, or a hosted Indic API
- [x] Write the first Hinglish and value-heavy tasks (AI-drafted, native-reviewed)

## Open questions (from the brief)

- [x] Name and licence: **vaad**, Apache-2.0.
- [x] Which base models: Qwen3.5-4B + Llama-3.2-3B (both licences allow redistributing quants;
      Llama needs a "Built with Llama" attribution).
- [x] Who are the native-speaker reviewers? Two for the data (names in `checked_by`); more are
      needed for the lexicons and for inter-annotator agreement
- [ ] Which strong tier for the demo?
