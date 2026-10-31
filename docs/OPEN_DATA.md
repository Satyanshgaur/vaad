# Open data: what exists, what it tells us, what it cannot replace

Searched 2026-10-31 (Kaggle, Hugging Face, ACL/arXiv). Reproduce the counts with
`scripts/fetch_open_data.sh`, `scripts/open_data_prevalence.py` and `scripts/open_data_kal.py`. All
datasets used are CC BY 4.0; downloaded outside the repo and never committed. Cite and attribute
them in any release.

## Usable now

| Dataset | What it is | Licence | Use |
|---|---|---|---|
| **MASSIVE** (Amazon, `AmazonScience/massive` 1.1), `hi-IN` | 16,521 voice-assistant commands in **Devanagari**, 60 intents, slots for `date`, `time`, `timeofday`, `currency_name`, **parallel to English with the same ids** | CC BY 4.0 | times and dates evaluation; the "kal" resolver gold; prevalence |
| **COMI-LINGUA** (`LingoIITGN/COMI-LINGUA`) | 376K annotated Hinglish instances (Roman and Devanagari), social-media text | CC BY-4.0 | prevalence in typed Roman Hinglish |
| **FLEURS** (`google/fleurs`), `hi_in` | 2,120 read Wikipedia sentences with audio, raw and normalized transcripts | CC BY-4.0 | how ASR and transcripts treat plain numbers; audio for a Sarvam/Whisper number check |

Not usable (checked): the Kaggle Hinglish sets I found are tiny (a 20-dialogue set), or
labelled for cyberbullying or sarcasm, or have no stated licence for reuse; no Kaggle credentials are
configured here either. CST5/Hinglish-TOP (Hindi-English task-oriented parsing, 10.9K queries) is
a good fit in domain but I did not locate a public download. Kathbath (CC BY 4.0, 1,684 hours,
`transcription_n2w` suggests numbers written as words) and IndicVoices (7K+ hours, extempore and
conversational) are on Hugging Face **gated**: accepting their terms needs your decision, and I have
not accepted any on your behalf. Vistaar: no licence or transcript format found.

## What the counts say (rough: parser-based, unvalidated, "ek"/"do" over-counted)

| Source | Texts | Any number | Digits | Plain number word | Word + sau/hazaar/lakh/crore | Fraction word (dedh, sava, saade, paune...) |
|---|---|---|---|---|---|---|
| MASSIVE hi-IN, all | 16,521 | 17.1% | ~0% | 16.5% | 0.8% | 0.2% |
| MASSIVE hi-IN, time slot | 1,073 | 86.8% | ~0% | 83.1% | 2.1% | 2.8% |
| MASSIVE hi-IN, currency slot | 172 | 22.1% | ~0% | 21.5% | 0.6% | 0% |
| COMI-LINGUA TN (Roman) | 24,547 | 28.1% | 20.7% | 9.0% | 0.4% | 0.04% |
| FLEURS hi_in | 2,120 | 44.0% | 19.7% | 30.5% | 0.2% | 0% |

What this means:
1. **In voice-assistant Hindi, numbers are usually words** ("पांच बजे", "पंद्रह मिनट"): 83% of the
   time-slot commands have a spoken number word and none has digits. (MASSIVE's Hindi was written by
   translators, so this is the *transcript* convention, not necessarily what an ASR returns.)
2. **In typed Roman Hinglish, digits dominate** (20.7% of social-media texts have digits, 9.0% have
   number words): a typed deployment sees fewer spoken forms.
3. **The hard forms are rare in general text**: fractions are 0.2% and lakh/crore/hazaar/sau phrases
   0.8% of assistant commands, 0.4% / 0.04% of social text. They are *domain* phenomena (money,
   weights, delivery); none of these corpora is a payments or logistics corpus, so none of them tells us
   how often they matter where the product is meant to be used.
4. **Colloquial clock times exist but are few**: 25 MASSIVE commands use "सवा/साढ़े/पौने ... बजे".

## "kal": free gold for the resolver

410 MASSIVE Hindi utterances contain "कल". The English parallel says which sense: **367 tomorrow,
43 yesterday, 21 neither**. That is a labelled set for the tense resolver (10.5% are the past
reading, so a "always future" baseline is wrong about one in ten), mostly calendar (194), alarm
(63) and weather (59) requests. Also 845 "आज" (today) and a handful of "परसों". Gold comes from the
English text, so it is independent of anything we wrote.

## First use: the times and dates evaluation

`scripts/eval_massive.py` scores the time and date parsers on MASSIVE hi-IN by partition (train to
develop, dev to check, test once). Results are in RESULTS R15: "kal" resolved correctly 97.1% of the
time when it decides (test, 35 of 69 decided; always-tomorrow is 92.8%) and clock times 100% exact when
confident (test, 69 of 90 confident).

## What this lets us shrink, and what it cannot

- **Times and dates evaluation: use MASSIVE.** 1,073 time-slot and 2,563 date-slot utterances with
  English parallels (digits spelled out: "nine am", "next tuesday"). Gold values come from a small
  deterministic English time/date reader checked by hand on a sample, so no one has to write or
  record time and date phrasing from scratch.
- **Number-word coverage:** FLEURS and MASSIVE are an independent check that the Devanagari
  lexicon covers real transcripts (every word we fail to read is a bug or a missing variant).
- **Prevalence claims:** we can already say fractions and big-number words are rare in general
  Hindi and Hinglish text. That narrows the product to *domains where they are common*.

Still needs new data (smaller than planned in DATA_COLLECTION.md):
- Money, delivery and measurement requests with dedh/sava/saade/lakh/crore, **in Roman script**
  (no open set has them), typed: floor **100 messages from 5 people** (was 200 from 8).
- What a real ASR returns for those spoken values, and noisy or phone-call audio: floor **120
  utterances from 3 speakers** (was 300 from 5-6). FLEURS can supply Sarvam/Whisper checks on plain
  numbers (about 100 utterances, roughly Rs 20 at Rs 30 per audio hour) without any recording.
- The independent held-out half still has to come from people who never saw the lexicons.
