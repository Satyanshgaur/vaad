# Data: sources, construction, review, splits

Everything a datasheet or the paper's data section needs. Counts are from the files in
`harness/tasks/` (checked 2026-10-29); the hashes are in `harness/tasks/SPLITS.lock`.

## Task sets

| Set | Language | What it is | Source and licence |
|---|---|---|---|
| `bfcl_en` | English | Gorilla BFCL v4 *live* questions | Gorilla BFCL, Apache-2.0 |
| `bfcl_hi` | Hindi (Devanagari) | BFCL v2 *live* questions, translated | NVIDIA BFCL-Hi, CC-BY-4.0, machine-translated by NVIDIA |
| `bfcl_hinglish` | Hinglish (Roman script) | Rewrites of the English questions | Written for this project (see below) |
| `value_heavy` | en, hi, hinglish | 50 scenarios x 3 languages, 11 tools | Written for this project (see below) |

- **Pairs:** tasks sharing a `pair_id` are the same task in different languages. Splitting is
  on `pair_id`, so a task and its translations always land in the same split.
- **BFCL construction** (`harness/importers/bfcl.py`): BFCL-Hi is read as raw JSON from
  `nvidia/BFCL-Hi` revision `500e3062d11fb68a5aa5a878404d62ffaf15f869`; Gorilla at commit
  `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`. **Both languages use BFCL-Hi's (v2) function
  definitions and ground truth**; only the English question text comes from v4. Pairs whose
  ground truth differs between v2 and v4 are dropped, so the English question still matches
  the answer.
- **Sample:** 150 pairs, drawn with seed `20261024`: 60 simple, 50 multiple, 7 parallel,
  8 parallel_multiple, 25 irrelevance. BFCL `live_relevance` is not used (no ground truth).
- **Categories:** `irrelevance` and `clarify` tasks have no valid call; the correct behaviour
  is to call nothing (or, with the gateway, to ask back).

## Hinglish rewrites (`bfcl_hinglish`)

Romanized, code-mixed rewrites of the English questions, keyed by `pair_id`
(`harness/sources/bfcl_hinglish.yaml`, kept in the private repo).

Rewrite rules: keep the meaning and every value the ground truth needs; keep quoted strings,
names, URLs and IDs exactly as in English; numbers, dates and times **may be spoken in
Hinglish** ("teen April", "dedh", "bees"), because handling those is the point of the project;
typical chat spelling, no diacritics.

| Batch | Rewrites | Split | Drafted by | Review |
|---|---|---|---|---|
| 1 | 50 | dev + test | Claude (AI assistant), 2026-10-24 | AI pass (Gemini 3.8 Flash via `agy`), then native Hindi speaker (Sarthak Mehta), 2026-10-29 |
| 2 | 39 | dev | Claude, 2026-10-26 | same as batch 1 |
| 3 | 51 | test only | Claude, 2026-10-29 | AI pass only. **Not native-checked** (`native_checked: false`) |

- **Totals:** 140 rewrites (57 dev, 83 test); 89 native-reviewed, 51 AI-reviewed only.
- **Not 150:** 4 test tasks have non-English originals (Korean appliance command, Thai prompt,
  Chinese prompt, one meta-prompt), so they have no Hinglish version.
- **Review outcome:** the native reviewer changed 9 of 89 rewrites (mostly "X ki directed" to
  "X ki direct ki hui", one state name added to match the expected city, one capitalization,
  one redundant "Shaam"). The AI pass flagged 2 of 89 (one pronoun case, one in test),
  and 2 of 51 in batch 3 (an ambiguous bare "hi", a gender agreement); all were applied.
- **Rejected suggestions:** the AI reviewer's six requests to replace spoken numbers with
  digits (batch 1 dev pass) were not applied, because they remove the intended difficulty.

## Value-heavy set (`value_heavy`)

50 scenarios, each in English, Hindi and Hinglish with the same expected call
(`harness/sources/value_heavy.yaml`). Domain: Indian e-commerce, banking, delivery and
booking. Reference date is fixed at **Saturday 2026-10-24** and stated in the system message.
Phone numbers are made up.

- **Tools (11):** ship_order, track_order, send_money, pay_bill, apply_loan, recharge_mobile,
  order_grocery, book_appointment, book_train, set_reminder, get_statement.
- **Deliberate traps:** "do" = two / give ("do kilo cheeni bhej do"); "saath" = sixty / with;
  "kal" = tomorrow / yesterday; "parson" both ways; spoken digits ("double nine");
  fractions (sava 1.25, saade +0.5, paune -0.25, dedh 1.5, dhai 2.5, aadha 0.5, paav 0.25);
  lakh / crore.
- **Clarify scenarios:** 9 of 150 tasks (3 scenarios x 3 languages) have no valid call; asking
  back is the only correct answer.
- **Review:** drafted by Claude 2026-10-24; checked by an AI pass (50/50 ok), then by a native
  Hindi speaker (Movendu Singh), 2026-10-29: 5 Hindi and 6 Hinglish rewordings applied
  (mostly turning "chahiye" or "bharna hai" into a direct request). One suggestion was **not**
  applied: `statement-01` ("1 October se kal tak"), where the reviewer found "kal" ambiguous.
  That ambiguity is the trap, so it stays. Another change (`loan-05` Hindi, "चौबीस" to "24")
  was applied although it slightly eases that item.

## Splits (frozen, then deliberately re-locked)

- **Rule:** `sha256("vaad-split-v1:" + pair_id)` -> first 8 bytes -> fraction; `< 0.4` is dev,
  otherwise test. Never change the salt.
- **One extra rule:** a BFCL pair whose question text repeats a dev task is dropped from test.
- **Current counts** (`SPLITS.lock`, after the 2026-10-29 re-lock):

| File | Dev | Test |
|---|---|---|
| bfcl_en | 62 | 87 |
| bfcl_hi | 62 | 87 |
| bfcl_hinglish | 57 | 83 |
| value_heavy | 69 (23 scenarios x 3) | 81 (27 x 3) |
| **Total** | **250** | **338** |

  By language on dev: English 85, Hindi 85, Hinglish 80 (57 BFCL + 23 value-heavy).
- **G0 baseline used an earlier dev set:** 211 tasks, of which 41 Hinglish (18 + 23). The
  dev set has since grown and some text was corrected. **Any comparison of a gateway run to
  the G0 raw numbers must re-run the raw baseline on the current dev set.**
- **Re-lock history:** (1) G0, 2026-10-24: 211 dev / 286 test. (2) 2026-10-29: native-review
  fixes, then batch 3. Only the Hinglish and value-heavy files changed; `bfcl_en` and `bfcl_hi`
  hashes did not.

## Test-split handling ("hashed-private")

- Test tasks and the rewrite sources live in the private repo `Satyanshgaur/vaad-private`
  (`scripts/private_sync.sh`). The public repo has only `SPLITS.lock` and `test_ngrams.txt`
  (4,248 hashes of word 6-grams), so CI can run **gate 10** without the text.
- **Gate 10:** no 6-gram of any test user turn may appear in lexicons, prompts, tests or
  examples. It has already caught one accident (a test fixture that reused a test sentence).
- The test split is run **once per release**, at Phase 4, never to chase a number.
- Dev tasks and their `checked_by` fields are public; reviewer names appear there.

## Exposure of test content (state this in the paper)

- The test-split Hinglish rewrites and their English originals were sent to a third-party
  model service (Google Gemini, through the Antigravity `agy` CLI) for the AI review pass.
  The 51 batch-3 rewrites were *written* by an AI assistant (Claude). So "private" means
  "not published", not "never seen by any model provider".
- The Hindi test text (NVIDIA BFCL-Hi) and English test text (Gorilla BFCL) are already public
  upstream; only the sampling and the Hinglish/value-heavy text are new.
- The value-heavy test scenarios were also AI-drafted and AI-reviewed.

## Review artifacts (private repo, `review/`)

`hinglish_rewrites.csv` (89 rows), `hinglish_reviewed.csv` and `value_heavy_reviewed.csv`
(the reviewers' returned files), `value_heavy.csv`, `hinglish_rewrites_batch3.csv` (51 rows,
awaiting a native reviewer) and `REVIEWER_GUIDE.md`.

## Known data limitations

- Hindi is machine-translated (BFCL-Hi), so some of the Hindi gap may be translation
  noise rather than model weakness. The Hinglish and value-heavy sets are human-reviewed.
- Hinglish and value-heavy text was drafted by an AI and corrected by one native reviewer per
  set. No inter-annotator agreement has been measured yet (the brief asks for it on a sample).
- 51 test rewrites are not native-checked.
- BFCL live questions are English-centric tools; only value-heavy has Indian-context values.
- Reference-date tasks assume one fixed date (2026-10-24).
