# What the results mean, and where a defensible moat could be

Written 2026-10-31 after H1-H9, the typed-message batches and the open-data work. Research on moats is
opinion-heavy (blogs, newsletters); treat it as a lens, not as evidence.

## 1. Calibration: how much to believe each result

| Claim | Evidence | Confidence |
|---|---|---|
| Models of 3-4B fail on **spoken-form values** (dedh, saade, paune, lakh, kal/parso, colloquial times) by 52-65 pass^4 points against English | H1b, three families, pre-registered, paired CIs excluding 0 | **High** that it happens on this benchmark. **Medium** that it matters in practice (see below) |
| A prompt (7-27%) or translate-first (7%) does not fix it | H7, H6 | **Medium-high** (one prompt wording, one translator) |
| A deterministic normalizer recovers 87-114% on the dev set and cuts silent wrong values from ~0.5 to ~0 | H9, three models | **Medium-low as a size of effect.** Circular: same author as the lexicons, traps known to the parsers. High only that the *direction* is right |
| The parsers generalize to what people type | Held-out batch of 196 messages: they find 90-100% of the card values | **Medium** (card-driven, 7 writers) |
| Spoken-form numbers matter in **typed** Hinglish | 8.7-8.9% of card-driven messages; 0.4% of real friend chat | **Evidence says rarely.** The ambiguity (AM/PM, "kal") is the common problem |
| Spoken-form numbers matter in **voice** | Nothing measured yet | **Unknown** (the ASR check decides) |
| Hindi (Devanagari) tool calling is the bigger reliability problem | R9, R13: large gap, not a script problem, only partly the answer key | **Medium**; outside the product's scope |
| Compression and Indic calibration | Not supported (R3, R11, R14) | One model each, **low power** |

So the honest summary: *there is a real, large, reproducible failure of small models on spoken-form values, and a
simple deterministic layer removes most of it on the benchmark built to show it; whether that is a product depends
on how often real users produce those values, which is low for typed chat and still unmeasured for voice.* The expected
product-level effect on typed traffic is small (a few points at most); it is large only where such values are frequent.

## 2. What is not a moat

- **The parsers and lexicons.** I wrote them in hours with AI help; any competitor, or an ASR vendor, can do the same.
  Publishing them under Apache-2.0 makes this explicit.
- **Generic argument validation.** Schema checks, tool-input guardrails and gateways with pre-tool checks already
  exist (Guardrails AI, the OpenAI Agents SDK, TrueFoundry-style gateways). The grammar-and-retry layer is table stakes
  and did not improve accuracy.
- **Residency and "India-hosted".** Others offer it.

## 3. What research and our results suggest can last

1. **A private, growing test corpus of real expressions with independent native labels** ("tests are the new moat").
   It is what lets us say how well the layer works and catches regressions, and it is expensive to recreate:
   consented chats, card-driven batches, recordings, regional variants, held-out halves. We have the start of it.
2. **Calibrated trust.** The product's useful property is not "accuracy" but *confidence that means something*: when it
   says 0.9 it is right about 98% of the time (clock times 98-100%, "kal" 97% when it decides), and it says "ask"
   when it is not sure. A published **calibration card** and an **audit trail** per value (which words, which rule,
   which lexicon version, what decision) are what a regulated buyer can show a reviewer. This is the part a prompt
   or a bigger model cannot give.
3. **Distribution through the voice stack.** Plugins for Pipecat and LiveKit (the way Gnani and Sarvam publish
   theirs) put the layer where voice agents are built, ASR-agnostic and LLM-agnostic.
4. **A data flywheel from design partners:** real failures (new spoken forms, regional spellings, ASR error patterns)
   feed the lexicons and the private corpus. The mechanism must be privacy-safe (counts of unknown tokens, not
   transcripts).
5. **Speed of execution and openness** as trust: results, negatives and pre-registrations published.

Reality check from the research: no source documents a company defending itself by owning a benchmark alone, and
the Indian voice companies' reported moats are proprietary code-mixed call audio and on-prem deployment, which we
do not have. The realistic target is **permanence, not a wall**: be the trusted reference implementation and
evaluation for spoken values, with a corpus and partners that are hard to replicate quickly.

## 4. What we build, in this order (items 2 and 3 done 2026-10-31: docs/CALIBRATION.md and the audit trail in ARCHITECTURE.md)

1. **A model-in-the-loop evaluation on human-written text** (pre-registered as A6): tests whether the layer helps
   on text nobody tuned it on, and gives the honest effect size. Calibrates the claim.
2. **A reliability (calibration) card**: accuracy by confidence band for each parser, from the held-out data.
3. **An audit trail**: every checked argument records field, final value, source span, rule, confidence, lexicon
   version and decision, in the trace.
4. **A privacy-safe gap miner** and a contribution workflow for lexicon growth (unknown tokens next to baje, rupaye,
   kilo..., counts only).
5. Voice middleware and the ASR test, once recordings exist.
