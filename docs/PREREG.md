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
