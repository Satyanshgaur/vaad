# What we need from human reviewers

Everything below is something the author cannot do alone, because it needs a native Hindi/Hinglish speaker's
judgment or someone who has not seen our lexicons. Each item says what it unlocks. Items are ordered by value
for the paper and for trusting the product. Total for the first four: about 5 hours of one reviewer's time.

**Who counts as a reviewer.** A fluent native Hindi speaker who texts or speaks Hinglish daily. For R4 the
reviewer must **not** have seen `src/vaad/canon/lexicons/` or any of our results. Different people for R1 and
R5, so that R5 measures agreement.

**Conventions for every file.** CSVs in `private/review/`. Write only in the columns named. Do not rewrite
other columns. A blank cell means "no change". Reviewers are named only with their consent (see R7).

## R1. Check the 51 AI-only test rewrites (about 30 min)

- **File:** `private/review/hinglish_rewrites_batch3.csv`
- **Do:** for each row, is the Hinglish sentence natural, and does it keep the meaning, numbers and names of the
  English original? Fill `verdict (ok/fix)`, and for `fix` the `corrected_hinglish` column; add a `comment` if useful
  and your `reviewer` code.
- **Unlocks:** the "native-reviewed" claim for all 140 rewrites instead of 89; the test set is final only after
  this. Until done, results on those 51 are labelled AI-reviewed.

## R2. Rescoring audit (about 45 min)

- **File:** `private/review/rescore_audit.csv` (52 rows).
- **Do:** each row shows an expected value (`answer key`) and a model's output for a field. Is the output
  equivalent for the user's purpose (`equivalent? (yes / no)`)? Add a `comment` for every `no`.
- **Unlocks:** whether our field-aware rescoring agrees with a human, which decides whether the Hindi
  free-text-artifact numbers (13-27%) can be quoted.

## R3. Lexicon review (about 1.5 h)

- **File:** `private/review/lexicon_review.csv`, exported from the YAML lexicons by
  `python scripts/export_lexicon_review.py`.
- **Do:** each row is one word, its spelling, and the value we give it ("dedh" = 1.5, "paune" = -0.25 of the
  next unit). Mark `correct` (yes/no); for `no` give the right value in `right_value`. Add new rows (leave
  `source_file` blank) for words we are missing, including regional or colloquial forms (Delhi, Bihar, Rajasthan, Mumbai).
- **Unlocks:** lexicons stop being "AI-written, not native-reviewed" in the release notes; every missing word
  found is a recall gain.

## R4. Independent value-heavy set (about 3 writers x 1 h each)

- **Protocol:** `docs/DATA_COLLECTION.md` and the scenario cards in `docs/templates/scenario_cards.md`.
- **Do:** each writer writes about 60 messages as they naturally would, one per card variant, in
  `private/review/independent_<id>.csv`, filling `intended_value` themselves. They must not look at our
  lexicons or outputs first.
- **Unlocks:** the one measurement that removes the "same author wrote lexicons and tasks" objection: parser
  and normalizer accuracy on text we did not influence, scored once. Also feeds the gap miner (`vaad gaps`).
- **Needs:** at least 3 writers, mixed age and region; a fixed reference date stated on the sheet.

## R5. Agreement on a sample (about 30 min)

- **File:** `private/review/agreement_sample.csv` (30 rows drawn from rewrites already reviewed by someone else; the text shown is the version the first reviewer accepted, their verdict is hidden).
- **Do:** same task as R1, without seeing the first reviewer's verdict.
- **Unlocks:** an inter-annotator agreement number (Cohen's kappa) for the paper; reviewers' disagreements show
  which phrasings are ambiguous.

## R6. What should the system ask? (about 30 min)

- **File:** `private/review/ambiguity_judgments.csv` (60 made-up messages, no real chat, that we cannot decide, for example "kal" with
  no tense cue, "paanch baje" with no part of day).
- **Do:** say what you would understand (`reading_1`, `reading_2`), whether a human assistant would ask back
  (`would_ask` yes/no), and how sure you are (1-3).
- **Unlocks:** checks that our abstention (ask vs guess) matches people's. Today it is tuned on our own labels.

## R7. Naming, consent, credit

- Whether and how each reviewer is named in docs and the paper, and any compensation agreed. Nothing is named
  until the reviewer says yes. Existing reviewers' consent to be named is still **to confirm**
  (`docs/PAPER_NOTES.md`).

## R8. Decisions only the author can make

- Publish the datasets (BFCL-Hinglish rewrites, value-heavy set) and when; the test split stays hashed until
  the paper is out.
- Whether the PyPI package and a Hugging Face dataset go public after the GitHub release.

## Not needed now

Audio and recordings (v2, `docs/AUDIO_SPEC.md`). Deployment partners. More than three models.

## What we do with the returns

Merge the corrections, re-run only what they change (R1 and R3 re-run the test split's affected tasks and the
parser gold suite; R4 is scored once), append outcomes to `docs/RESULTS.md` and `docs/PREREG.md`, and update the
release notes' list of limits. Nothing is deleted from the history.
