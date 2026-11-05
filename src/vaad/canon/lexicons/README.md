# Lexicons

Hindi (Devanagari) and Hinglish (Romanized) word lists used by the canonicalizer.

Rules:

- One YAML file per value type. Keys are surface forms, values are canonical values.
- Every PR that touches this directory states **where the words came from** (own knowledge,
  a named native speaker, a licensed source). No words copied from the test split — gate 10
  checks this.
- Spelling variants of Romanized words are expected (`do`, `doh`; `teen`, `tin`); list each.

## Finding what is missing

`vaad gaps FILE.csv --column text --min-count 3` lists words that sit directly before a time, money,
quantity or duration anchor ("baje", "rupaye", "kilo", "ghante") and are in no lexicon. Output is word counts
only, and only for words seen at least `min-count` times, so you can run it on private chat and share the
result. Read each candidate: question words ("kitne") are not gaps; number spellings are, and go in the YAML
with a note on where they came from. On the two private text sets we have (about 100 anchor hits), it found
no missing number spellings.
