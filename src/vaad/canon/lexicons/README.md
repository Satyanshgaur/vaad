# Lexicons

Hindi (Devanagari) and Hinglish (Romanized) word lists used by the canonicalizer.

Rules:

- One YAML file per value type. Keys are surface forms, values are canonical values.
- Every PR that touches this directory states **where the words came from** (own knowledge,
  a named native speaker, a licensed source). No words copied from the test split — gate 10
  checks this.
- Spelling variants of Romanized words are expected (`do`, `doh`; `teen`, `tin`); list each.
