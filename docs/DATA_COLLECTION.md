# Collecting real requests and recordings

> **Read [OPEN_DATA.md](OPEN_DATA.md) first.** Open datasets (MASSIVE, COMI-LINGUA, FLEURS) already
> cover times, dates, the "kal" resolver and general prevalence, so the floors below are lower than
> the original targets: **typed 100 messages from 5 people** and **120 utterances from 3 speakers**,
> focused on money, delivery and measurement requests (where fractions and lakh/crore live).
> The original targets (200 messages, 300 utterances) are still the better size if people are
> available.

Two datasets decide the product (PLAN.md, "Evidence track"): **typed messages** (how often spoken-form
values appear in text chat at all) and **voice recordings** (what the ASR hands to the model, and
the independent test set). Both are written or spoken by native speakers who have **not seen the
lexicons, the trap list or the value-heavy file**. That is the whole point: it is what makes any
gain on them count as evidence.

## 1. Typed messages

**How many:** target **200** messages from **at least 8 people** (no more than 25 each, so no one
voice dominates). A useful floor is 100 from 5 people. If real, anonymized messages from a chat or
support log are available, add up to 100 more and keep them in a separate file (`real`), never
mixed with the prompted ones (`prompted`).

**What each person does:** takes scenario cards (`docs/templates/scenario_cards.md`, goals only,
values given as digits) and writes the message **the way they would send it to a WhatsApp bot or
voice assistant**: any Hindi/English mix, any script they normally use, no translating from the card,
and digits are fine if that is what they would really do. 8-25 messages each.

**Format:** one CSV or a Google Sheet, UTF-8, with the columns in
`docs/templates/typed_messages_template.csv`:

| Column | Meaning |
|---|---|
| `id` | `T001`... (assigned by the sheet) |
| `writer_id` | `w01`, `w02`... (not a name) |
| `source` | `prompted` or `real` |
| `scenario_id` | the card used (blank for `real`) |
| `written_on` | the date the message is written, `YYYY-MM-DD` (so "kal", "parson" can be resolved) |
| `message` | exactly what they would type; no editing afterwards |
| `intended_values` | what they meant, one `field=value` per value, `;` separated, e.g. `weight_kg=1.5; delivery_date=2026-11-02`. Dates as `YYYY-MM-DD`, money in rupees, times `HH:MM` 24-hour |
| `script` | `roman`, `devanagari` or `mixed` |

The writer fills `intended_values` themselves, because they know what they meant. For `real`
messages, a second native speaker fills it.

**Splits:** half the messages become the **tuning half** (used to build and tune the parser, dev
only); the other half is the **held-out half**, stored in the private repo and not opened by anyone
building the parser until the parser is frozen. It is scored once.

## 2. Recordings

**How many:** target **300 utterances** from **5-6 speakers** (about 50 each). The floor is 3
speakers x 40 = 120. Mix of men and women and of regions where Hindi is spoken (for example Delhi/UP,
Bihar, Mumbai, Rajasthan, and Hindi speakers from the south), because ASR errors vary a lot by accent.

**What each speaker does:** two parts.
- **Part A, about 40 utterances:** look at a scenario card and say the request in their own words, as if
  talking to a voice assistant. No script is read.
- **Part B, about 10 utterances:** read aloud 10 of the typed Hinglish messages from section 1 (written
  by someone else), so the same text can be compared before and after the ASR.

**Audio format (what is easiest and still usable):**
- One utterance per file, **3-15 seconds**, natural pace, one request each.
- **Best:** mono WAV, 16 kHz, 16-bit PCM.
- **Also fine:** a phone voice recorder app or **WhatsApp voice notes** (`.m4a`, `.ogg`/opus, `.mp3`): I convert
  them with ffmpeg. Do not edit, trim speech, or apply noise reduction.
- Quiet room for most; **5 of each speaker's utterances in a normal noisy place** (street, kitchen,
  fan) and, if possible, **a few over a real phone call** (8 kHz telephony is what voice agents get).
- File names: `spk01_A007.wav` (speaker, part, number).

**Manifest:** one row per file, `docs/templates/recordings_manifest_template.csv`:
`file, speaker_id, part, scenario_id, written_message_id (for part B), recorded_on, device,
environment (quiet/noisy/phone_call), intended_values`. Speaker details (region, gender, age band,
first language) go in one separate sheet keyed by `speaker_id`, never in file names.

**Cost to run through the ASR:** 300 utterances of about 8 seconds is about 40 minutes of audio. Sarvam
speech-to-text is Rs 30 per audio hour (new accounts get free credit), so a full pass over all of its
modes (transcribe, verbatim, codemix) costs roughly Rs 60, within the free credit. Gnani Vachana is
by request with unpublished pricing and is optional.

## 3. Consent, privacy and fairness (not optional)

- **Written consent from every contributor** before anything is collected, saying what the data is
  for (a research benchmark and a software library), who sees it, and whether the audio or text may
  ever be published. Default: **nothing raw is published**; only scores, aggregate statistics and
  (if each person agrees) the text of the messages.
- A voice recording is personal data under India's DPDP Act 2023. Store it in the private repo or on an
  encrypted disk, delete on request, and never put names, phone numbers, account numbers or addresses
  in a message. Scenario cards use made-up values; for `real` messages, redact before they reach us.
- Contributors are not asked for sensitive details and must be adults.
- **Pay or credit them.** Recording and writing 50 items is about an hour of someone's time. Agree
  a rate or a clear acknowledgement before starting; the author decides.
- Whoever writes the **held-out** half must not see this repo's lexicons, golden cases or the
  value-heavy file.

## 4. What I do with it

1. Count how often spoken-form values appear (typed, then after ASR), by type: fractions, lakh/crore,
   colloquial time, relative day, digits-as-words.
2. Run the ASR comparison (Sarvam modes, Whisper, optionally Gnani): how often an unresolved spoken
   value still reaches the model.
3. Tune the parser on the tuning half only; freeze; score the held-out half once; report the
   proceed/reposition gates in PLAN.md.
