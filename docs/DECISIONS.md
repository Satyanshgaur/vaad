# Decision log

Choices that shaped the results, with the reason. Newest last within each phase. If a paper
reviewer asks "why did you...", the answer should be here.

## Scope and framing

- **Name and licence:** vaad, Apache-2.0. Both base models' licences allow redistributing
  quants (Llama needs "Built with Llama" attribution and the licence copy).
- **Out-of-scope table in the brief is the contract.** New ideas go to GitHub issues labelled `v2`.
- **Lead with the language gap and wrong-value execution, not compression** (2026-10-25).
  Reason: G0 showed C1 (compression hurts Indic more) is not supported at 3-4B; the gap and
  the wrong-value rate hold at both precisions. The brief's fallback allowed exactly this.

## Evaluation design

- **Paired bootstrap instead of non-overlapping intervals** (G0). With 41 Hinglish dev tasks,
  non-overlap would need about a 30-point gain. A gain counts when the paired 95% CI of the
  per-task difference excludes 0.
- **pass^k alongside pass@1.** Reliability (all k trials correct) is the property an agent
  needs; pass@1 hides inconsistent behaviour.
- **4 seeds at temperature 0.7**, plus a temperature-0 pass for the smoke gate. Seeds 4-7 are
  a held-out reproducibility check, not extra data.
- **Thinking off for Qwen3.5.** A call takes about 7.9 s with thinking versus 2.69 s without,
  which would make the launch grid about 50 GPU hours.
- **Wrong-value execution is a first-class metric**, defined as schema-valid, right
  functions, wrong values. It is the failure that costs money in a real agent, and schema
  validity alone (about 95%) hides it.
- **Flagged trials count as schema-valid**, so flag rate is always reported next to pass@1.
- **Launch target written at G0 and never moved** (see METHODS.md), checked once on test.
- **Scoring is BFCL-style exact match with acceptable-value lists**, case-insensitive on
  strings, strict on booleans, 1e-9 on numbers. Unparseable model output is a failed trial,
  not a crash (fix in PR 3).

## Data

- **BFCL-Hi for Hindi, Gorilla BFCL for English, both on BFCL v2 functions and answers.**
  The v4 questions can drift from the v2 answers, so pairs whose ground truth differs are dropped.
- **Hinglish is a rewrite of the English task, not a translation of the Hindi one**, so a
  Hinglish task has the same tools and answers as its English and Hindi siblings.
- **Spoken numbers, dates and times stay in the Hinglish rewrites** ("teen April", "dedh").
  Normalizing them is the gateway's job, so removing them would remove the test. The AI
  reviewer's six requests to write digits instead were rejected for this reason.
- **Split on `pair_id`, 40/60 dev/test, salt frozen**, so translations never straddle the split.
- **Hashed-private test split:** text in a private repo, hashes and 6-gram hashes public, so
  gate 10 runs in public CI. The test split is run once per release.
- **Skipped 4 non-English-origin test tasks** for Hinglish (Korean, Thai, Chinese, a
  meta-prompt) rather than invent a meaning. Hinglish therefore stops at 140, not 150.
- **The 51 batch-3 test rewrites are tagged AI-reviewed only.** `native_checked` is a
  separate flag from `checked_by`, so an AI reviewer's name can never read as a native check.
  Names of AI reviewers are recorded as such.
- **`statement-01` keeps "kal"** although a reviewer found it ambiguous: statement end dates
  are past, so context should resolve it, and that is the trap. This is also the paper's
  "how 'kal' ambiguity is resolved" analysis.
- **Re-lock once, deliberately,** after review rather than after every edit. A re-lock needs
  new hashes, a private sync and a PR note.
- **Reviewers are credited in `checked_by`** (they supplied the names and the review).
  Confirm they are happy to be named publicly before release.

## Infrastructure

- **llama.cpp commit `df9beac`, one llama-server per model**, `--jinja` for native tool calls.
- **Qwen3.5-0.8B for the CI smoke gate**, on CPU, with the prebuilt release `b11860`, which
  is the same commit as the local build. Tolerance 0.10 on schema-valid rate: a 0.8B model is
  noisy, and the gate exists to catch a broken request path.
- **Gateway off is a byte-faithful passthrough** (raw bytes, streaming allowed, no trace), so
  "gateway off" in an ablation really equals "no gateway".
- **Gateway on refuses `stream: true`** (400) until the response can be rewritten in a stream.
- **A rejected call is retried once, as a user turn**, because many chat templates reject a
  tool-result turn without a matching assistant call.
- **Validation always uses the client's original schemas**, never the tightened ones, so
  tightening can only constrain generation, not redefine correctness.
- **Schema tightening is conservative:** patterns and enums are inferred only from explicit
  wording in the field description. Strict versus loose date grammar is a switch because the
  brief predicted that a strict grammar can force a confident wrong date; the ablation decides
  the default. Currently `strict`.
- **Patterns use `[0-9]`, not `\d`,** for llama.cpp's grammar converter.
- **Leakage guard caught a test sentence in a test fixture** (2026-10-29); fixtures must use
  neutral text.

- **Cap llama-server's prompt cache at 2048 MiB** (2026-10-30) after two out-of-memory kills
  of long runs; recorded in REPRODUCE.md because earlier runs used the 8192 MiB default.

- **Strict date grammar stays the default** (2026-10-30): G1 showed no difference between strict
  and loose (RESULTS R7), so there is no reason to give up the guaranteed ISO format.

## Process

- One change per PR with a conventional-commit title; squash-free merge commits.
- PRs are merged when CI is green and the work matches the plan; artifacts (publications,
  datasets, models, posts) are reviewed by the author before anything is published.
- AI assistance: Claude drafted code, dataset text and docs; Gemini 3.8 Flash (via Antigravity
  `agy`) was used as a reviewer. Both are disclosed in PAPER_NOTES.md.
