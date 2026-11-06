# Draft: spoken-value grounding for small local models in Hindi/Hinglish

Working draft, 2026-11-05. Numbers come from `docs/RESULTS.md` (R-numbers in brackets). Items marked (test run done, R21) This is a preprint skeleton, not a
submission. Authors, acknowledgements and the dataset release are the author's decisions.

## Abstract (draft)

Small quantized language models (3-4B parameters) run locally are attractive for Indian-language agents, but
their tool calls fail on spoken-form values: "dedh hazaar" becomes 15,000, "saade aath baje" becomes 20:30,
an unmarked "kal" becomes today. We measure this on three model families with pre-registered hypotheses and
paired bootstrap intervals. Natural Hinglish phrasing alone does **not** make tool calling less consistent
(H1 fails on three families), but spoken-form values cost 52-65 pass^4 points against English (H1b). We then
add a deterministic, abstaining normalizer: Hindi/Hinglish parsers for numbers, money, quantities, clock
times, durations, phones and tense-aware dates, each value with a span and a calibrated confidence. On
189 held-out human-typed tasks it raises pass^4 by 16-22 points on all three models (CIs above 0) and cuts
wrong values from 23-42% to 7-9% when it is allowed to ask. Outputs at confidence >= 0.9 were right 97-100% of
the time on held-out data. We also report what did not work: grammar constraints plus retry, prompting,
translate-first, and compression without an imatrix at 3-4B. Limits: text only, three small models, lexicons
not natively reviewed, tasks written to contain values.

## 1. Introduction

- Problem: small local models in Indian agents; the value must be exactly right (money, time, phone).
- Contribution list: (1) measurement with pre-registration, including negative results; (2) a deterministic
  normalizer with abstention and an audit trail; (3) calibration evidence; (4) resources: Hinglish rewrites of
  BFCL, value-heavy set, parser gold suite (release decision pending).
- What we do not claim: speech, large models, general Hinglish understanding.

## 2. Related work (to be verified before submission, PAPER_NOTES.md)

Lost in Execution (multilingual tool calling); BFCL and BFCL-Hi; tau-bench (pass^k); indic-punct and NeMo
inverse text normalization; Sarvam ASR number normalization; quantization in translation (Marie and Fujita).
Position: none documents Roman-script fractions, colloquial times, tense-aware relative dates, abstention or
tool-schema verification; a vendor may do it privately.

## 3. Data and method

- Tasks: BFCL English, BFCL-Hi (machine translated), BFCL-Hinglish (140 rewrites; 89 native-reviewed, 51
  AI-reviewed only), value-heavy (50 scenarios x languages), 189 held-out human-typed tasks, MASSIVE hi-IN for
  parser tests (DATA.md).
- Metrics: pass^4 over 4 seeds at temperature 0.7, paired bootstrap 95% CI over tasks, wrong-value and flag
  rates. Hypotheses and amendments A1-A7 in PREREG.md, outcomes appended and never edited.
- Normalizer: `annotate` writes the parsed value after each spoken-form span ("dedh hazaar [=1500]");
  `verify` checks the model's tool-call argument against the turn (agree / silent repair / retry / flag);
  `both` does both. Decisions are gated by calibrated confidence; below 0.6 it asks.
- Models: Qwen3.5-4B, Granite-4.0-micro, Ministral-3-3B at Q4_K_M, llama.cpp, one RTX 3050.

## 4. Results

### 4.1 The gap [R11]
H1 natural Hinglish: gaps -8.8, -5.3, -7.0, all CIs include 0. H1b value-heavy: -65.2 [-82.6, -43.5], -60.9,
-52.2. Hindi (machine translated) gap -18 to -44; only 13-27% is the free-text answer-key artifact [R9].

### 4.2 What does not close it
Strong prompt: Hinglish +12 but English -6 [R2]. Worked-conversion prompt recovers 27/7/8% of the gap with
English dropping 3-10 points [R12]. Romanizing hurts Qwen by 19-26 points; translate-first closes 26-40% of
the Hindi gap and 7% of the spoken-value gap [R13]. Schema tightening plus retry: no accuracy gain [R7].
Imatrix calibration versus tensor allocation not separable at this sample size; Q3 vs Q4 without imatrix
costs about nothing [R11, R14].

### 4.3 The normalizer
- Dev (value-heavy Hinglish): `both` recovers 87/114/100% of the gap; `annotate` alone 87/107/100%; the
  pre-registered English-regression clause **fails** for `both` on all three (CI lower bounds -11.3, -11.3,
  -8.1) [R19]. Dev is circular (same author as the lexicons).
- Held-out human-typed (189 tasks, new writers): annotate - off +22.2 [16.4, 28.6], +19.0, +16.4; both - off
  +21.7, +28.0, +11.6; wrong values 23/42/34% -> 7/9/7% with `both` at the price of a 7-19% ask rate [R20].
- **Test split (A7, R21):** value-heavy annotate - off +21.0 / +28.4 / +16.0 (all CIs above 0), `both`
  +24.7 / +44.4 / +17.3; value-heavy Hinglish +37 to +59. BFCL English -3.4 / -3.4 / 0.0 (annotate), -5.7 / -5.7 /
  0.0 (both), lower bounds -6.9 to -12.6: the English clause fails. Pooled Hinglish for Qwen `both` vs best
  baseline +7.3 [-1.8, +15.5]: the +10 launch target is not met. Worked prompt: no detectable effect.

### 4.4 Parsers and calibration [R15-R17, CALIBRATION.md]
MASSIVE hi-IN (test, run once): "kal" direction 97.1% when decided (34/35; baseline 92.8%), clock times 100%
exact when confident (69/69). Confidence >= 0.9 is right 97-100% on held-out data; one miscalibrated band
(unmarked multi-number amounts, ~50% right) was found by the card and changed to ask.

### 4.5 Prevalence
Spoken-form numbers are about 9% of card-driven typed messages and 0.4% of real friend chat (aggregate
only): the gain applies where messages carry values, such as orders, payments, reminders and voice agents.

## 5. Discussion and limitations

Text only; ASR errors untested (v2). Three models of 3-4B. Lexicons and tasks share an author; R4 in
REVIEWER_NEEDS.md would remove that. `both` costs English accuracy on dev; `annotate` is the safer default
and `both` the safer-for-money mode. One reference date. The held-out typed tasks are card-driven.

## 6. Reproducibility

Frozen splits (`SPLITS.lock`), commit hashes in each report, `docs/REPRODUCE.md`, `scripts/run_*.sh`,
audit trail in traces (offsets only).

## 7. Ethics and disclosure

AI assistance for drafting code, rewrites and docs (Claude); AI review (Gemini) is not native review.
Private chat used with consent, only as aggregates. Reviewer naming pending consent. Test split hashed until
the paper is out.

## Open before submission

Test-run table [T]; REVIEWER_NEEDS R1-R6; related-work check; figure set (gap by value kind, calibration
curve, ask-rate versus wrong-value); venue choice (arXiv, then an ACL/EMNLP workshop or NeurIPS D&B).
