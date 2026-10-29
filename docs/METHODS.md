# Methods: metrics, scoring and protocol

Precise definitions, as implemented, so the paper's method section can be written from here.
Code: `harness/score.py`, `harness/metrics.py`, `harness/run.py`.

## One trial

A trial is one task, one condition, one seed. The harness posts the task's messages and tools
to `{base_url}/v1/chat/completions` with `temperature`, `max_tokens = 512`, `seed`, and (for
Qwen3.5) `chat_template_kwargs: {enable_thinking: false}`. Reported runs use **temperature
0.7 and seeds 0-3**; the CI smoke gate uses temperature 0 and seed 0. A condition is
model x quant x gateway setting (x system prompt).

llama-server answers HTTP 500 when it cannot parse the model's tool-call text. That is a model
failure, not a harness error: the trial is scored incorrect and schema-invalid, and the server
message is stored in the `error` field.

## Per-trial outcomes

- **correct** (`score.calls_match`): the predicted calls are exactly the expected calls, in any
  order. For each pair: same function name; no argument that is not expected (a hallucinated
  argument fails); every expected argument present (unless listed `optional`); each value
  equals one of the acceptable values listed for it. Value equality: numbers within 1e-9;
  booleans strictly; strings compared after strip and case-fold; lists elementwise; dicts by
  key. Fields marked `free_text` only need a non-empty string. For `irrelevance` and `clarify`
  tasks the expected list is empty, so a trial is correct only when **no call** is made.
  Parallel groups of more than 7 calls use a greedy match instead of all permutations.
- **schema-valid:** the arguments parsed as JSON, every call names an offered tool, and the
  arguments satisfy that tool's JSON Schema (Draft 2020-12). Tool schemas that are themselves
  invalid JSON Schema (a few BFCL ones) are skipped, so they never count against a model.
- **wrong-value execution** (the business-critical failure): at least one call was made, it is
  schema-valid, the multiset of function names matches the expected one, **and the call is
  not correct**. A downstream system would execute it with a wrong value.
- **flagged:** the gateway answered with a clarification (`vaad_flag`) instead of a call.
  Nothing is executed. A flagged trial counts as schema-valid and not wrong-value, so the
  **flag rate must always be read beside pass@1**: flagging everything would otherwise look
  perfect. On `irrelevance` and `clarify` tasks a flag is a correct answer.
- **latency:** wall-clock milliseconds of the request, p50 and p95 reported.

## Aggregate metrics

For a task with n trials and c correct:

- **pass@k** = 1 - C(n-c, k) / C(n, k): at least one of k trials succeeds.
  pass@1 is the mean per-trial accuracy.
- **pass^k** = C(c, k) / C(n, k): **all** k trials succeed (the reliability metric from
  tau-bench). With n = k = 4 it is 1 only if all four seeds pass. Reported as pass^4.
- Both are unbiased per-task estimators, averaged over tasks, reported per language.

## Uncertainty and significance

- **Interval:** percentile bootstrap over **tasks** (10,000 resamples, alpha 0.05, seed 0);
  every number in the results carries a 95% interval.
- **Comparing two conditions:** the **paired** bootstrap of the per-task difference
  (`paired_bootstrap_ci`), both conditions run on the same tasks. A gain is real when the lower
  bound is above 0. This replaced the brief's "non-overlapping intervals" rule at G0, because
  with 41 Hinglish dev tasks that rule would require a gain of about 30 points.
- **Reproducibility check:** the same seeds give identical results (llama-server is
  deterministic per seed); a fresh seed set (4-7) must land inside every interval.

## Conditions

| Name | Meaning |
|---|---|
| raw | model as served, no gateway, no system prompt (`gateway: off`) |
| strong prompt | raw + `harness/prompts/strong_system.txt` (answer in English machine formats; ask if ambiguous) |
| grammar-strict / grammar-loose | gateway with schema tightening, validation and one retry; strict forces ISO dates in the grammar, loose leaves dates free |
| (Phase 2) canon, router, full | canonicalizer only, router only, everything |
| (Phase 4) blind retry | one retry without canonicalization, required baseline in the brief |

Baselines to beat (from the brief): the raw model; the raw model with a strong system prompt;
one guided retry without canonicalization. Beating only the raw model is not a convincing
claim.

## Launch target (fixed at G0, 2026-10-24, never moved)

Model Qwen3.5-4B Q4_K_M, checked once on the test split at Phase 4:

| Metric | Target |
|---|---|
| Hinglish pass^4, gateway on vs best baseline | at least best baseline + 10 points, paired 95% CI of the gain above 0 |
| English pass^4, gateway on vs raw | paired 95% CI lower bound of the change at least -3 points |
| Hinglish wrong-value rate | below raw, paired 95% CI of the change below 0 |
| Added p50 latency, canonicalizer only | under 20 ms |

"Best baseline" is the better of raw and the strong prompt, per language.

## Gate 9 (smoke) protocol

50 dev tasks chosen deterministically (seed `20261029`, round-robin over every source x
language), Qwen3.5-0.8B Q8_0 on CPU, temperature 0, seed 0. Fails when the schema-valid rate
is more than 0.10 below `harness/reports/smoke_baseline.json`. It detects a broken request
path, not a quality change.
