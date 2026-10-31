# Changelog

All notable changes to this project are documented here. Versions follow SemVer.

## [Unreleased]

### Added
- Phase 2: `canon` times, dates, durations (tense- and field-aware "kal"), evaluated on MASSIVE hi-IN.
- Open-data survey, prevalence counts and the collection protocol (docs/OPEN_DATA.md, DATA_COLLECTION.md).
- Phase 0: BFCL-Hi/BFCL paired tasks, 140 Hinglish rewrites, the 50-scenario value-heavy set
  (native-reviewed except 51 test rewrites), frozen dev/test split, G0 baseline and compression grid.
- Phase 1: OpenAI-compatible proxy (byte-faithful passthrough when off), JSONL tracing, schema
  tightening, post-generation validation, one guided retry, `vaad_flag` clarification, gates 7 and 9.
- Docs: results log, methods, data sheet, architecture, decision log, reproduction guide, paper notes.
- Project scaffold: package layout, typed stage interfaces, example config.
- Harness: task schema, pass@k / pass^k, bootstrap 95% intervals, deterministic dev/test split
  with lock file, BFCL-style call scorer, leakage guard (gate 10).
- CI with gates 1, 2, 3 and 10.
