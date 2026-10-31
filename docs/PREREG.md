# Pre-registration: decision rules for the Phase 1 follow-up experiments

Written and merged **before** the experiments below were run. Do not edit it afterwards;
append a dated amendment at the end instead (and say why). Anything not covered here is
exploratory and must be labelled that way in the paper.

Date: 2026-10-30. Scope: **dev split only**. The test split is not touched.
The grammar ablation (strict vs loose, `g1-strict` / `g1-loose`) was started before this file
and is not covered by it.

## Common protocol

- Dev split as locked by `harness/tasks/SPLITS.lock` on the date above (250 tasks).
- 4 seeds (0-3), temperature 0.7, `max_tokens` 512, thinking off, one llama-server per model,
  llama.cpp `df9beac`, raw condition (no gateway, no system prompt).
- Metric: pass^4 per task, mean over tasks. Intervals: percentile bootstrap over **tasks**,
  10,000 resamples, 95%. Comparisons: **paired** on matched `pair_id`s.
  "CI excludes 0" means the whole 95% interval is on one side of 0.
- A model **qualifies** for a hypothesis only if its English BFCL pass^4 is at least 0.40
  (below that, a gap in a language cannot be measured: floor effect). Non-qualifying models are
  still reported.
- Three families at 3-4B, all Q4_K_M, as the main models. Order of preference if one fails to
  produce tool calls at all: Qwen3.5-4B (unsloth Q4_K_M, already in use), IBM Granite-4.0-micro
  (3B, Apache-2.0, official GGUF), Phi-4-mini-instruct (3.8B, MIT), Llama-3.2-3B (already in
  use; expected to be below the floor from G0). All four are run; hypotheses are evaluated on the
  **qualifying** ones. If fewer than 3 qualify, every hypothesis below is reported as
  "inconclusive" rather than decided on 2 models.
- Gemma-3-4B was considered and rejected: it has no native tool-call template in llama.cpp.
- Hinglish BFCL = the 57 dev rewrites. They are the only matched-pairs test of "natural"
  Hinglish; value-heavy (23 scenarios) is analysed separately and not pooled.

## H1. The consistency gap exists

Question: is Hinglish less reliable than English on matched BFCL tasks?

- Statistic: paired pass^4 difference, Hinglish minus English, on the 57 matched BFCL pairs.
- **Stands** if the CI excludes 0 (negative) for at least **2 of the qualifying models**.
- **Does not stand** if the CI includes 0 for at least 2 qualifying models.
- Otherwise: inconclusive.
- The same statistic is reported for value-heavy (23 scenarios) as H1b with the same rule.
  Existing evidence before the rule: Qwen3.5-4B (gateway on) -12.3 [-22.8, -1.8] on 57 pairs;
  Q4/Q8 G0 runs on 18 pairs all included 0.

## H2. Hindi gap vs scoring

Question: how much of the BFCL Hindi-vs-English gap is an answer-key artifact (English
expected strings for free-text content)?

Field-aware rescoring (implemented in `harness/rescore.py`, rules fixed here):

1. Every expected argument field is classified from the tool schema by deterministic rules
   (type, `enum`, `format`, field name, description) into:
   - **identifier / format**: enums, IDs, URLs, slugs, file paths, commands, dates, times,
     numbers, booleans, codes, keys. Scored exactly as today.
   - **name**: person, place and brand names. Accepted if the prediction matches the expected
     name after transliteration (Devanagari to Latin, then a normalized phonetic edit
     similarity >= 0.80, or a case-folded exact match).
   - **free text**: titles, content, queries, messages, descriptions, labels. Accepted if
     exact (as today) **or** the prediction is semantically equivalent (rule 3).
   - Default for any field the rules cannot place: **identifier** (strict). The rules can only
     loosen scoring where the field is clearly name or free text.
2. Rescoring is applied identically to every language, model and run, so English can gain too.
3. Free-text equivalence: cosine similarity of multilingual embeddings (bge-m3, Q8_0 GGUF,
   served by llama-server) between the prediction and the closest expected string is at least
   tau, **and** every digit sequence in the expected string appears in the prediction.
   No LLM judge is used.
4. **Human audit before any claim:** 50 cases (about 20 accepted just above tau, 20 rejected
   just below, 10 random), labelled equivalent / not equivalent by a native speaker other than
   the system's author, using `private/review/rescore_audit.csv`. tau is the smallest value
   from {0.70, 0.75, 0.80, 0.85, 0.90} whose audit precision (accepted cases judged equivalent)
   is at least 0.95. If none reaches 0.95, or no audit is done, **rescored results are
   exploratory and cannot support a claim.** Until the audit exists, tau = 0.80 is used for
   exploration only. The same audit includes about 10 name cases for the transliteration rule.
5. Classifier audit: all (tool, field) pairs classified as free text or name are listed in
   `harness/field_classes.yaml` for review; a field the reviewer moves to identifier is moved
   and the rescoring re-run (no other change).

Hypothesis:
- **The Hindi gap is largely a scoring artifact** if, for at least 2 qualifying models, the
  rescored paired BFCL Hindi-minus-English pass^4 gap is at most **50%** of the original gap's
  size, **and** the audit passed.
- **The Hindi gap persists** if, for at least 2 qualifying models, the rescored gap still has a
  CI excluding 0 and is at least 10 points in size.
- Otherwise: partially explained / inconclusive.

## H3. Rankings under the new scoring

- Models are ranked by BFCL pass^4 per language (en, hi, hinglish) under the original and the
  rescored metric.
- **A ranking change is reported** only when the audit passed and a pairwise ordering of two
  qualifying models flips with the paired CI of the rescored difference excluding 0 in the new
  direction. It is **not** headlined otherwise, and needs at least 3 qualifying models.

## H4. Compression at Q3 (claim C1, controlled)

- Qwen3.5-4B quantized by us from the BF16 GGUF with `llama-quantize`, **no importance matrix**,
  to Q4_K_M and Q3_K_M. The paper must say this makes Q3_K_M harsher than most published Q3
  files, which usually use an imatrix. Also run the existing unsloth Q4_K_M (imatrix) as an
  exploratory comparison only.
- For each language L in {en, hi, hinglish}, the drop D_L = pass^4(Q4) - pass^4(Q3) per task,
  on all dev tasks of that language (BFCL and value-heavy pooled, matched across the two quants).
- **C1 is supported at Q3** if the CI of (D_hinglish - D_en) **or** (D_hi - D_en) excludes 0
  (positive), using independent task bootstraps for the two languages, **and** the point
  estimate of that difference is at least 5 points.
- Otherwise C1 is reported as not supported at Q3 for this model. One model only: say so.

## H5. Small-model size point (descriptive)

- Qwen3.5-0.8B Q8_0 on the full dev set. No hypothesis. If its overall schema-valid rate is
  below 50% it is reported as "does not produce usable tool calls", and no language gap is
  claimed from it.

## What each outcome means for the project

- **H1 stands and H2 says artifact:** the paper's finding is that Hinglish costs reliability
  (consistency) even on natural requests, while the Hindi gap is mostly an answer-key artifact.
  Continue Phase 2 as planned.
- **H1 does not stand, value-heavy gap (H1b) stands:** natural Hinglish is fine; spoken-form
  values are the whole problem. Narrow the claim to spoken numbers, dates and times; keep the
  canonicalizer; lead with the resource (C3) and the targeted method.
- **Neither stands:** there is no robust problem at this scale for typed or spoken Hinglish.
  Stop Phase 2 as a method paper; publish the benchmark and the negative result as an
  evaluation note, and revisit the target user (voice versus typed) before any further build.
- **H4 supports C1:** add compression back as a headline. If not, it stays an analysis.

## Deferred (v2)

- Multi-turn conversations (needs new tasks).
- Voice clips through Sarvam or Gnani, and a corpus of real Hinglish requests (consent and API
  cost); the question of voice versus typed stays open.
- Models above 4B, quants below Q3, models below 0.8B.

## Amendments

### A1 (2026-10-30, before any audit): transliteration applies across scripts only

The name rule said a prediction is accepted "after transliteration ... or a case-folded exact
match". Inspecting rescored **English** trials showed the phonetic fallback also accepting
same-script near-misses (`Rutherford, NJ` for `Rutherford`, `Corte Madera` for `Corte Madera,
CA`), which are format errors in the answer key and not transliterations. Clarified: the phonetic
fallback applies **only when the prediction contains Devanagari**. Latin predictions must match
exactly (case-folded). Nothing else in the rules changes. The change was made after seeing the
first rescored numbers on two models but before any audit and before any claim; the numbers
reported before the amendment are superseded and are not used.

### A2 (2026-10-30, before the replacement model was run): a third qualifying family

Results so far (RESULTS R10): **Phi-4-mini made 0 tool calls in 880 trials that expected one.** Its
embedded chat template takes tools as a field on the system message and has no OpenAI-style
`tools` handling, so llama.cpp never shows it the tools: a setup incompatibility, not evidence
about the model. **Llama-3.2-3B** is below the English floor (BFCL pass^4 0.33) and emits
schema-invalid calls 55% of the time. That leaves two independent qualifying families (Qwen3.5-4B,
Granite-4.0-micro); the no-imatrix Qwen quant is the same family and does not count as a third.
Under "if fewer than 3 qualify, every hypothesis is inconclusive" the H1-H3 verdicts would stay
inconclusive.

Amendment: add **Ministral-3-3B-Instruct-2512 (Mistral, Apache-2.0, official GGUF, native tool
calling, Q4_K_M)** as the third family and run it exactly like the others (raw, current dev set,
4 seeds, temperature 0.7). It is chosen for being a different family at the same size with
OpenAI-style tool support, **before** any result from it is seen, and it counts toward the
qualification rule whatever it scores; if it also falls below the floor, H1-H3 stay
inconclusive and are reported that way. Phi-4-mini and Llama are reported as non-qualifying.
No other rule changes. A fourth candidate, if this one fails to produce tool calls, is
SmolLM3-3B (Apache-2.0).

## Outcome (2026-10-30)

Recorded after all runs finished; the verdict table with numbers is RESULTS R11.
- H1: **does not stand** (all three qualifying families include 0).
- H1b: **stands** (all three exclude 0, -52 to -65 points).
- H2: "largely an artifact" **not met** (73-104% of the gap remains); exploratory, audit pending.
- H3: **not met** (no ordering flip).
- H4: **C1 not supported at Q3** for the one model tested.
- H5: descriptive only.

Per "What each outcome means": H1 does not stand and H1b stands, so natural Hinglish is not less
consistent than English at this scale, and spoken-form values are the problem. The project narrows
to spoken numbers, dates and times; the canonicalizer is kept; the resource (C3) and the targeted
method lead.

### A3 (2026-10-31, before any of these runs): Hindi diagnosis, prompts, and calibration

Motivation, from RESULTS R11: the Hindi gap persists after rescoring; Ministral answers Hindi in
prose instead of calling a tool in 34% of call-needing trials (English 7%) with zero parser
failures; H1b survives only against the raw model; and the "14.5-point imatrix effect" compared our
no-imatrix Q4_K_M with the unsloth Q4_K_M, which also differs from the llama.cpp default in **99 of
426 tensors** (48 `ssm_alpha`/`ssm_beta` kept at Q8_0, others at Q5_K), so calibration and tensor
allocation are confounded. Everything below uses the same protocol as the common protocol above
(dev only, 4 seeds, temperature 0.7, qualifying families Qwen3.5-4B, Granite-4.0-micro,
Ministral-3-3B at Q4_K_M, raw scoring primary; rescored numbers are exploratory until the audit).
"gap" = pass^4(English) - pass^4(the language), matched `pair_id`s.

**H6. Is the Hindi gap a script problem or a translation-quality problem?**
- `hi-roman` (script control): the Hindi user turn with every Devanagari span deterministically
  romanized (`harness/romanize.py`: ITRANS, then lower-cased with long-vowel marks dropped), Latin
  spans, digits and names untouched. Same words, Roman script. Tasks: BFCL-Hi (62) and Hindi
  value-heavy (23).
- `translate-first`: a first call to the same model (temperature 0, "translate to English,
  keep numbers, names and quoted text exactly, output only the translation"), then the normal
  tool call on the translation. Tasks: Hindi and Hinglish, BFCL and value-heavy (165). The
  translation is made once per task and reused for the 4 seeds.
- For each model, delta = pass^4(condition) - pass^4(raw) on BFCL-Hi (paired, 62 tasks).
  **Script problem** if delta(`hi-roman`) >= 50% of the gap and its CI excludes 0 on >= 2 of 3
  models; **not a script problem** if its CI includes 0 on >= 2 of 3. **Translate-first closes most
  of the gap** if delta >= 50% of the gap with the CI excluding 0 on >= 2 of 3 (BFCL-Hi), reported
  separately for Hinglish value-heavy against its own gap. Otherwise inconclusive.
- Also reported, not decided: the no-tool-call, malformed-JSON and parse-failure fractions per
  language and condition (infrastructure check).

**H7. Does H1b survive a prompt?**
- Conditions: `prompt-strong` (`harness/prompts/strong_system.txt`) and `prompt-worked`
  (`harness/prompts/worked_conversions.txt`: the strong prompt plus a short generic table of
  spoken-form conversions, e.g. dedh = 1.5, dhai = 2.5, sava = 1.25, saade teen = 3.5, paune char =
  3.75, lakh = 100000, crore = 10000000, kal/parson = tomorrow/yesterday or day after
  tomorrow/day before yesterday by tense). Tasks: all value-heavy (69), BFCL English (62) and BFCL
  Hinglish (57).
- **A prompt recovers most of H1b** if, for value-heavy Hinglish, delta(prompt - raw) >= 50% of
  the gap with the CI excluding 0 on >= 2 of 3 models, **and** BFCL English does not regress (the
  CI lower bound of the paired change is above -5 points). The worked prompt overlaps the dev
  traps by design, so its dev number is a ceiling and is circular; it cannot support a claim about
  a canonicalizer without the independent test set below.
- If a prompt recovers most of H1b, the canonicalizer's claimed value is restricted to the residual
  and to guarantees a prompt cannot give (determinism, abstention, auditability).

**H8. Calibration versus tensor allocation (one model, Qwen3.5-4B).** Arms, all built by us from the
BF16 file at the same llama.cpp commit, Q4_K_M, full dev, 4 seeds:
- A0 default allocation, no imatrix (exists, `f1-qwen3.5-4b-noimat-Q4_K_M`);
- A1 default allocation + English imatrix; A2 default allocation + Indic imatrix;
- A3 unsloth's tensor allocation (copied with `--tensor-type-file`) + no imatrix.
- Calibration corpora, ~80 chunks of 512 tokens each, no task text or evaluation data: English =
  English Wikipedia sample; Indic = Hindi Wikipedia sample in Devanagari plus the same text
  romanized with `harness/romanize.py` (half and half). Sources and sizes recorded in the repo.
- **Calibration matters** if A1 - A0 has a CI excluding 0 on BFCL English; **allocation matters**
  if A3 - A0 does. **Indic calibration helps** if A2 - A1 is >= +5 points on BFCL Hindi or Hinglish
  or value-heavy Hinglish with the CI excluding 0 and English not worse by more than 3 points.
  Reported next to unsloth - A0 (-14.5 on English BFCL) as a decomposition.

**Independent test set (blocker for any canonicalizer claim).** The value-heavy dev and test sets
and the lexicons share an author. No canonicalizer gain on value-heavy counts as evidence. A claim
requires a new set written by native speakers who have not seen the lexicons or the trap list:
fresh spoken-style requests with gold values, split into tuning and held-out halves, scored once.
No author is assigned yet. **Real typed requests** (50-100) are likewise not collected yet.

### A4 (2026-10-31, before reading any A3 result): lean run plan

The A3 runs were estimated at about 5 GPU hours and only one part decides whether the
canonicalizer is worth building. Scope cut, made **without having looked at any result** from the A3
runs (the Qwen romanized-Hindi run had finished but was not opened):
- **H7:** only the **worked-conversion prompt** is run, on value-heavy (69 tasks) and BFCL English
  (62, the regression check), on all three qualifying models. The strong prompt is dropped: the
  worked prompt contains it, so if the worked prompt cannot recover most of the gap the strong
  prompt cannot either. BFCL Hinglish is dropped (H1 already failed there). The H7 rule is
  unchanged. (The G0 strong-prompt result on the old dev set stays as background.)
- **H6:** the script control (`hi-roman`) runs on Qwen (done) and Ministral (to test the
  no-tool-call collapse); **translate-first** runs on Qwen only, on BFCL-Hi and value-heavy
  Hindi and Hinglish (BFCL Hinglish dropped). Granite is not run for H6. The H6 rules need
  "2 of 3 models", so with fewer models H6 can only be **reported descriptively**, not decided; a
  decision needs Granite and Ministral to be added later.
- H8 (calibration versus allocation) and the independent test set are unchanged.

### Outcome of H7 (2026-10-31)
Worked-conversion prompt, three families: recovers 27% (Qwen, CI excludes 0), 7% (Granite) and 8%
(Ministral) of the value-heavy Hinglish gap, with English BFCL changing by -3.2, -9.7 and -6.5.
**Not met** (RESULTS R12). The canonicalizer's value is not reduced to a residual by prompting.

### Outcome of H6 (2026-10-31, descriptive: fewer than 3 models by A4)
Script control: romanizing Hindi **hurts** Qwen (-19 and -26 points, CIs exclude 0) and leaves
Ministral unchanged, so the Hindi gap is not a script/tokenization problem. Translate-first (Qwen
only) closes 26% (BFCL-Hi) and 40% (value-heavy Hindi) of the Hindi gap and 7% of the Hinglish
spoken-value gap: "closes most" is **not met** on any set. RESULTS R13.

### Outcome of H8 (2026-10-31, one model)
Calibration, allocation and Indic-specific calibration effects are each **not significant** on BFCL
English (+4.8, +6.5 and +3.2 points, all CIs include 0); the total unsloth effect (+14.5 [+6.5,
+24.2]) is roughly the sum of allocation and calibration and cannot be split with 62 tasks.
"Indic calibration helps" is **not met** (best case BFCL Hinglish +7.0 [-1.8, +17.5]). RESULTS R14.

### A5 (2026-10-31, before any canonicalizer run): does the normalizer close the spoken-value gap?

Conditions (Qwen3.5-4B, Granite-4.0-micro, Ministral-3-3B; Q4_K_M; dev set, 4 seeds, temperature
0.7; through the gateway with grammar tightening **off** and the guided retry **on**; reference
date fixed at 2026-10-24): `canon.mode` = `off` (the control through the same gateway), `annotate`,
`verify`, `both`. Tasks: value-heavy (69) and BFCL English (62, the regression check). Statistic:
paired pass^4 of each mode minus `off`, per set and language.

**H9. The normalizer recovers most of the spoken-value gap.** Primary mode: **`both`** (named before any
result). Holds if, for value-heavy Hinglish, the paired gain over `off` is >= **50%** of the raw
Hinglish-vs-English gap with the CI excluding 0 on **>= 2 of 3** models, and BFCL English does not
regress (CI lower bound above -5 points). `annotate` and `verify` are reported as the ablation.
Also reported: flag rate and wrong-value rate per mode.

**Circularity (stated up front):** the value-heavy dev set and the lexicons share an author and the
parsers were written knowing the trap list, so this is a **dev estimate and an optimistic ceiling**,
not evidence. The claim requires the independent held-out set (PLAN, evidence track). The value-heavy
test split is not touched here.
