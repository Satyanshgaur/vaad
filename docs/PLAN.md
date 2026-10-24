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
4. Report bootstrap 95% intervals. A gain counts only when the intervals do not overlap
   (`harness.metrics.intervals_overlap`).
5. Freeze model file hashes, quant files and prompts in every results file.
6. The out-of-scope table in the brief is the contract. New ideas go into GitHub issues
   labelled `v2`.
7. One change per PR, with a conventional-commit title. Use the PR template.

## Launch target (written at G0, then never moved)

| Metric | Baseline (dev) | Target |
|---|---|---|
| Hinglish pass^4, 4-bit model, gateway off → on | _TBD Week 1_ | _baseline + ≥10 pts (placeholder)_ |
| English pass^4 with gateway | _TBD_ | 95% CI overlaps the baseline |
| Wrong-value execution rate | _TBD_ | below the baseline |
| Added p50 latency, canonicalizer only | n/a | < 20 ms |

Measured seconds per call: _TBD_ → launch grid budget: _TBD_ GPU-hours. The brief assumed
3 s/call, ~24k calls and ~20 h.

---

## Phase 0: Setup and baseline (Week 1, ~18 h) → G0

**Repo and CI** (done in the initial scaffold)
- [x] uv project, src layout, ruff, mypy, pytest config
- [x] Typed stage interfaces: `server/`, `router/`, `grammar/`, `canon/`
- [x] Harness core: `schema.py`, `metrics.py`, `split.py`, `score.py`, `leakage.py`
- [x] CI gates 1, 2, 3 and 10, plus the split-lock check
- [ ] Push the branch, open the first PR, confirm CI is green on GitHub

**Backend**
- [ ] Build llama.cpp with CUDA (`cmake -B build -DGGML_CUDA=ON && cmake --build build -j`)
- [ ] Shortlist models with native tool-calling templates that fit 6 GB at Q8. Candidates:
      Qwen2.5-3B / Qwen3-4B, Llama-3.2-3B, Phi-4-mini, a 1.5–2B model, and a ~0.5B model
      for the CI smoke gate
- [ ] Check that each one emits tool calls with `llama-server --jinja -ngl 99`
- [ ] Record the GGUF files and SHA256 hashes in `harness/models.yaml`
- [ ] Time one call and fill in the budget above. If it takes more than 6 s per call, use the
      fallback: one model on the full grid locally and the second on Kaggle

**Task sets** (format: `harness.schema.Task`, one JSON line per task)
- [ ] `bfcl_hi`: loader that reads the BFCL-Hi JSON files directly (not via `datasets`).
      Sample ~150 tasks across simple, multiple, parallel and relevance
- [ ] `bfcl_en`: the paired Gorilla BFCL originals. **Confirm the licence first**
- [ ] `bfcl_hinglish`: Romanized, code-mixed rewrites of the same `pair_id`s. Start with 50
      and reach 150 by Week 3
- [ ] `value_heavy`: own tools (order, payment, delivery, booking) where the arguments are
      amounts, dates, phone numbers and units. 50 tasks × 3 languages to start
- [ ] Put raw files in `data/raw/`, then
      `python -m harness.split assign data/raw harness/tasks && python -m harness.split lock harness/tasks`
- [ ] Decide the test-split release policy: hashed and private until the paper, or released
      with a canary string. Write the decision here: _TBD_

**Harness**
- [ ] `run.run_trial`: call the backend, parse `tool_calls`, score with `score.calls_match`
- [ ] Wrong-value detection: right function, schema-valid, but a value in `value_fields` is wrong
- [ ] Report writer: `harness/reports/<version>/results.csv` plus JSONL traces
- [ ] Summary table: pass@1, pass^4, schema-valid, wrong-value, flag rate, p50/p95 latency,
      each with a 95% CI, broken down by language

**Baseline**
- [ ] Raw model on dev, 4 seeds, run **twice**
- [ ] Strong-prompt baseline (`harness/prompts/strong_system.txt`)
- [ ] Fill in the launch target table above

**G0 exit:** the two raw runs agree within their intervals, `SPLITS.lock` is committed, and
the launch target is written down.
**Fallback:** if Hinglish pass^4 is already close to English, move the claim to smaller or
4-bit models, or lead with the wrong-value execution rate.

## Phase 1: Proxy, grammar, CI (Weeks 2–3, ~30 h) → G1

**Week 2: proxy**
- [ ] `server/backend.py`: httpx `AsyncClient` per backend, with timeouts and error mapping
- [ ] `server/routes.py`: `/v1/chat/completions` (non-streaming, with tools) and `/v1/models`
- [ ] `gateway_enabled: false` gives a byte-faithful passthrough
- [ ] One JSONL trace per request: lang, tier, raw args, canonical args, decision, ms per stage
- [ ] Gate 7: contract tests in `tests/integration/` using a `respx`-mocked backend. Check the
      OpenAI response shape and that passthrough with the gateway off changes nothing
- [ ] Gate 9: smoke eval on 50 dev tasks with the ~0.5B model on the CI CPU, 1 seed. Compare
      the schema-valid rate to the stored `harness/reports/smoke_baseline.json`
- [ ] Kaggle notebook (a): reproduce the baseline on free T4s

**Week 3: grammar and repair**
- [ ] `grammar/tighten.py`: add `pattern`, `enum` and `maxLength`. Dates get an ISO pattern.
      Numbers stay numbers. Drop keywords llama.cpp does not support
- [ ] `grammar/validate.py`: check again after generation (the jsonschema validator already exists)
- [ ] Guided retry: one retry with the validator errors added to the prompt
- [ ] Flag response: an assistant message carrying the clarification text plus a `vaad_flag`
      field, instead of a `tool_call`
- [ ] Ablation switch: strict date grammar versus loose grammar plus canonicalization

**G1 exit:** passthrough is identical to calling the raw backend, the schema-valid rate is at
least 99% with grammar on, and gates 1–9 run in CI.

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

## Things only you can do

- [ ] Build llama.cpp and download the candidate GGUFs (needs your GPU)
- [ ] Find 2–3 native Hinglish speakers to check a task sample and the lexicons
- [ ] Confirm the Gorilla BFCL licence and each base model's licence for redistributing quants
- [ ] Choose the strong tier for the demo: a local 8-bit model on Kaggle, or a hosted Indic API
- [ ] Write the first Hinglish and value-heavy tasks (an assistant can draft them, but a human
      must check them)

## Open questions (from the brief)

- [ ] Which two base models? Decide in Week 1.
- [x] Name and licence: **vaad**, Apache-2.0.
- [ ] Who are the native-speaker reviewers?
- [ ] Which strong tier for the demo?
