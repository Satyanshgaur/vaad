# Paper notes

A working file for the write-up: claims and the evidence each needs, the table and figure
inventory with source files, threats to validity, disclosures, related work and open items.
Status words are honest as of 2026-10-29.

## Working title and contribution

*Lost in Normalization: Making Small Compressed Models Reliable at Hinglish Tool Calling*
(placeholder). The contribution is the dataset, the measured finding and the method together,
not any one artifact.

## Claims and evidence status

| # | Claim | Evidence needed | Status |
|---|---|---|---|
| C1 | Compression hurts Hindi/Hinglish tool-call reliability more than English | grid with intervals, 2+ model families | **Not supported** at 3-4B (R3). Report as an analysis. Needs the Phase 3 controlled std-vs-Indic imatrix quants to say anything about calibration |
| C2 | Schema-aware, confidence-gated canonicalization recovers most of the gap, beating prompting, grammar alone and blind retry | ablations on the **test** split, run once | open (Phase 2-4). Baselines so far: raw, strong prompt (R1, R2). Grammar-only and retry in progress (R7) |
| C3 | Resources: BFCL-Hinglish, value-heavy set, canonicalization gold set | datasheets, native-speaker agreement on a sample | datasets exist and are native-reviewed (one reviewer per set); gold set not started; agreement not measured |
| C4 | Analyses: when grammar constraints hurt; how "kal" is resolved; whether Indic calibration helps | per-field-type breakdowns | one early observation of the strict-grammar confident-wrong date (R6); rest open |

New finding to lead with (measured, R1): **English 0.82 vs Hinglish 0.34 pass^4**, with about a
third of Hindi/Hinglish calls executing with a wrong value, at about 95% schema validity.

## Tables and figures (source files)

| Item | Content | Source |
|---|---|---|
| Table: language gap | pass@1, pass^4, schema-valid, wrong-value by language | `harness/reports/g0-qwen3.5-4b-Q4_K_M/raw-a/summary.json` |
| Table: compression grid | 2 models x 2 quants x 3 languages | `harness/reports/g0-*/raw-a/summary.json` |
| Table: strong prompt | paired change vs raw | `.../prompt` vs `.../raw-a` |
| Table: gateway ablations | raw, prompt, grammar-only, canon-only, router-only, full, blind retry | Phase 4, test split |
| Figure: failure taxonomy | wrong-value by field type (amount, date, time, phone, unit) | needs per-field breakdown in `results.jsonl` (`value_fields` is on every task) |
| Figure: flag rate vs accuracy | trade-off as thresholds vary | Phase 2-4 traces |
| Table: dataset statistics | counts per set, split, language, category | DATA.md |
| Latency table | p50/p95 per condition, canonicalizer added ms | R4, gate 8 |

## Threats to validity (write these into the paper)

1. **Dev-set drift.** G0 numbers are on the first 211-task dev set (41 Hinglish tasks); dev
   is now 250 tasks (80 Hinglish) with corrected text. Raw baselines must be re-run on the
   final dev set before any comparison, and on test for the claims.
2. **Small Hinglish sample.** 80 dev, 83+ test Hinglish tasks (value-heavy tasks are 23 and
   27 scenarios). Intervals are wide; use paired tests.
3. **Machine-translated Hindi** (BFCL-Hi) may add noise; Hinglish and value-heavy are human
   reviewed. Treat the Hindi-vs-Hinglish difference with care.
4. **Mixed provenance of Hinglish text:** AI-drafted, one native reviewer per set, 51 test
   rewrites AI-reviewed only, no inter-annotator agreement yet. Qualify any
   "native-reviewed" claim with the counts in DATA.md.
5. **Test-split exposure** to model providers (DATA.md): the hashed-private policy protects
   against web scraping and accidental tuning, not against provider-side logging of text sent
   for AI review.
6. **Contamination of BFCL itself:** BFCL and BFCL-Hi are public; the base models may have seen
   them. The value-heavy set and the Hinglish rewrites are new.
7. **One hardware and build;** temperature 0.7, 4 seeds; thinking off; exact-match scoring
   with case-insensitive strings (a capitalization difference scores as correct).
8. **Benchmark tools are not Indian-context.** Only value-heavy has rupee amounts, lakh/crore,
   Indian phone numbers and relative dates.
9. **Single reference date** (2026-10-24) for relative-date tasks.
10. **Model scope:** 3-4B models. C1 might hold at smaller sizes or harder quants (Q2/Q3);
    this is untested.
11. **Researcher degrees of freedom:** thresholds and lexicons tuned on dev only; the test run
    is a single run with the target fixed beforehand (METHODS.md). Log any deviation.

## Disclosures

- **AI assistance:** the code, dataset drafts (Hinglish rewrites, value-heavy scenarios) and
  docs were drafted with Claude (Anthropic). AI review used Gemini 3.8 Flash through the
  Antigravity CLI. Humans reviewed the data (below); code was reviewed through CI and PRs.
- **Native-speaker review:** Sarthak Mehta (bfcl_hinglish, 89 rewrites) and Movendu Singh
  (value_heavy, 50 scenarios), 2026-10-29. Compensation and consent to be named: **to confirm**.
- **Licences:** BFCL-Hi CC-BY-4.0 (NVIDIA); Gorilla BFCL Apache-2.0; Qwen3.5 Apache-2.0;
  Llama 3.2 community licence (attribution required); code Apache-2.0.
- **Use of datasets:** hashed-private test split; if released after the paper, say so and
  release the text with the checksums.

## Related work to position against (from the brief; verify before claiming novelty)

- Luo et al., *Lost in Execution* (multilingual tool calling at full precision)
- BFCL-Hi (NVIDIA) and the Berkeley Function-Calling Leaderboard (Gorilla)
- KiranaBench, hinglish-caller-bench, QuantClaw
- Marie and Fujita (quantization in translation)
- NVIDIA NeMo Hindi inverse text normalization (reference or fallback for Devanagari spoken forms)
- tau-bench (the pass^k reliability metric)
- llama.cpp JSON-schema grammar docs and Liquid AI's notes on constrained tool calling

Literature check still to do (brief, "Where to look"): ACL Anthology / arXiv cs.CL for
"code-mixed function calling", "Hinglish tool use", "inverse text normalization Hinglish",
"quantization tool calling" (last 18 months); Semantic Scholar citations of the closest
papers; Hugging Face datasets ("Hinglish", "function calling Hindi", "BFCL"); GitHub
("hinglish tool call", "hindi ITN", "indic normalization"). Email the closest authors after G2.

## Venues (from the brief)

arXiv preprint at launch; then NeurIPS 2027 Evaluations & Datasets track or an ACL 2027
workshop. A co-author from a reply after G2 would help.

## Open analysis questions

- Does a strict date grammar hurt (confident wrong dates) or help? (R7 decides the default.)
- How often does "kal" resolve correctly from tense versus tool semantics versus needing a flag?
- Flag rate versus wrong-value rate as thresholds move (the useful operating point).
- Does Indic-calibrated imatrix change tool-call reliability, controlled for everything else?
- Which field types carry the gap (amount, date, time, phone, unit)?
- Does the gap shrink at 7-8B, and grow at Q2/Q3?
- Inter-annotator agreement on a sample of the Hinglish rewrites.

## Numbers to recompute before submission

Everything in RESULTS.md R1-R3 on the final dev set; the whole test table; the agreement
statistic; latency on the final build. Keep the commit hash and `SPLITS.lock` hash of each run.
