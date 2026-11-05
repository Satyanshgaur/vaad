# Audio we need

What recordings would let us test the product's real premise: **a spoken Hindi/Hinglish value survives ASR
and the normalizer, and the tool call comes out right (or we ask).** Everything here is a request, not a
result. Nothing is recorded yet.

## 1. What we are testing

Chain: speaker says a value -> ASR transcript -> normalizer (`annotate`/`both`) -> tool call. The text results
(RESULTS R19, R20) start from clean typed text. Audio adds ASR errors: a misheard digit, "saade" dropped,
"baje" heard as "bhaje", Devanagari versus Roman output, numerals versus words. We need to know how many
values survive.

## 2. Two sources, in priority order

1. **Public speech with reference transcripts** (IndicVoices, Kathbath, MUCS). Mine utterances whose
   transcript contains a value our parsers find; the parse of the transcript is silver gold. No recording work
   for you. Needs the gated terms accepted by you.
2. **Your own recordings** (below). Needed because public speech rarely contains commands like "kal subah
   saade aath baje ka reminder laga do".

## 3. Your own recordings: the spec

| Item | Requirement |
|---|---|
| Utterances | 120 minimum, 300 good |
| Speakers | 3 minimum, 6 good; mix of men and women, at least two regions or accents |
| Length | 3-12 seconds each, one utterance per file |
| Content | One request that contains **at least one value** (see section 4). Natural, not read aloud like a list |
| Language mix | About 40% Hinglish in Roman-style speech, 30% Hindi, 30% mixed with English tool words |
| Format | WAV, 16 kHz or higher, mono, 16-bit PCM. Phone voice memos are fine if converted. No MP3 if avoidable |
| Naming | `spk01_S07_003.wav` = speaker, scenario card, take. No real names in file names |
| Environment | Mostly quiet room, plus about 20% with real background (street, kitchen, fan, car). Mark which |
| Device | Phone mic held normally; also 20% on a cheap earphone mic. Mark which |
| Speed | Normal speaking pace; a few fast ones are welcome |
| Disfluency | Keep "umm", restarts and self-corrections ("teen... nahi, chaar baje"). Do not re-record them away |

## 4. What each utterance must contain

Use the scenario cards (`docs/templates/scenario_cards.md`, S01-S28) as the prompts so the gold is known.
The coverage we need, minimum count per kind:

| Value kind | Examples of what is said | Min utterances |
|---|---|---|
| Amount (rupees) | "dedh sau rupaye", "sava do lakh", "paune teen hazaar" | 40 |
| Fractions and halves | "dedh", "dhai", "sava", "saade", "paune" | 25 |
| Quantity + unit | "adhai kilo", "do darjan", "paanch litre" | 30 |
| Clock time | "saade aath baje", "paune chaar", "shaam ke saat" | 40 |
| Relative date | "kal", "parso", "agle somvar", "is hafte ke end tak" | 40 |
| Phone number | said digit by digit or in pairs, with "double" and "triple" | 20 |
| Duration | "dedh ghanta", "paanch minute baad" | 15 |
| Ambiguity on purpose | "kal" with no tense cue, "paanch baje" with no am/pm | 20 |

An utterance can hold two kinds (amount + date). The ambiguous ones matter most: they test whether we ask
instead of guessing.

## 5. Per-utterance label sheet (CSV)

One row per file, filled by the speaker or whoever scripts it:

| Column | Meaning |
|---|---|
| `file` | file name |
| `speaker` | `spk01`... (no names) |
| `scenario` | card id, e.g. S07 |
| `intended_text` | what the speaker meant to say, in their own spelling |
| `gold_value` | the value: `1500`, `20:30`, `2026-11-03`, `+91...` |
| `gold_kind` | amount / time / date / phone / quantity / duration |
| `ambiguous` | yes/no (should the system ask?) |
| `ref_date` | the date assumed for "kal" (we use one fixed reference day per session) |
| `noise` | quiet / background |
| `device` | phone / earphone |
| `consent` | yes (see section 7) |

If a speaker misspoke, they mark the row `misspoke` and we drop it from scoring.

## 6. Splits and use

- **Dev** (about 40%): used to tune ASR text handling, lexicons and thresholds.
- **Held-out** (about 60%): different speakers from dev where possible; scored once, never read while tuning.
  This is the same discipline as the typed batches.

Metrics (pre-registered before running): value survives ASR (parser finds the gold value in the ASR text);
final tool-call correct (pass^k) with and without the normalizer; wrong-value rate; ask rate on ambiguous
rows. Reported per ASR system, since vendors differ.

## 7. Consent and privacy

- Each speaker agrees in writing that recordings are used for this evaluation. Say whether audio may be
  published; default is **no, private**.
- No names, phone numbers or addresses of real people in utterances. Phone numbers spoken must be made up.
- Audio and labels live in the private repo only. Public docs get aggregates, never clips or transcripts.
- Anyone who wants out can have their files deleted.

## 8. Who and how much

Three friends doing 50-100 utterances each in an afternoon is enough to start. Sending a phone voice memo
per card, using the CSV above, is the lowest-effort route.

## 9. Not needed

Studio quality, long conversations, singing or accented-English-only clips, TTS-generated audio (it tests
nothing about real ASR errors; it is only a cheap smoke test).

## 10. What this will not tell us

Real call-centre or WhatsApp-voice distributions; a few speakers give a pilot, not a benchmark. Say so in any
write-up.
