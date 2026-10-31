# Product, market and go-to-market

Written 2026-10-31 from our own results (RESULTS R9-R14) and a first round of web research.
**The research is shallow and mostly vendor marketing; every market claim below is a hypothesis to
test, not a finding.** Sources are listed at the end; items marked (unverified) rest on a single
vendor page or a search snippet.

## 1. The problem we can actually defend

Measured (dev set, three 3-4B families, Q4_K_M):
- Spoken-form values (dedh, saade teen, paune char, lakh/crore, parson/kal) cost **52-65 points of
  pass^4** against English on value-heavy tasks, on every model that can call tools (H1b).
- A worked-conversion prompt recovers **7-27%** of it and costs English BFCL 3-10 points (R12).
- Translate-first recovers **7%** (R13). Grammar plus retry alone slightly lowers accuracy (R8).
- Natural Hinglish phrasing without such values is **not** significantly less reliable than English
  (H1 does not stand, R11). The Hindi (Devanagari) gap is real, is not a script problem, and is only
  partly the answer key (R9, R13); it is a separate problem and not the product.

So the product is **spoken-value grounding**, not "Hinglish tool calling".

## 2. What exists today

| Layer | Examples | What it does for us |
|---|---|---|
| ASR with built-in inverse text normalization (ITN) | Sarvam Saaras v3 ("transcribe" mode returns digits, "verbatim" keeps words; Sarvam Edge on-device ASR has an ITN engine covering numbers, dates, currencies, temperatures), Smallest.ai and Soniox document ITN | Plain numbers ("nau paanch...") already arrive as digits from these engines. **This shrinks the voice opportunity** for cardinal numbers and phone digits. Not shown by their docs: fractions (dedh, sava, saade, paune), mixed lakh/crore phrasing, colloquial times, tense-dependent relative dates. |
| ASR without it | OpenAI Whisper transcribes spoken Hindi numbers as words | Open-source and on-device stacks need a normalizer. |
| Open-source ITN | indic-punct (WFST grammars, 11 Indic languages, Hindi included), NVIDIA NeMo-text-processing (Hindi row in the support matrix; ITN coverage unverified), kenpath/indic-text-normalization (unofficial extension) | Devanagari-centred, grammar-based; coverage of fractions, Roman-script Hinglish and abstention is undocumented. Prior art to cite and compare against. |
| Small libraries | `hindi-normalize` (MIT, zero dependencies, 2 commits, no stars): Devanagari number words to digits; no fractions, lakh/crore, money, times, relative dates or Roman script documented | Confirms the narrow gap: nothing public handles Roman-script Hinglish fractions, times and tense-aware dates together. |
| Date parsing | `dateparser` lists Hindi; quality of relative expressions such as "kal" is untested by us | A fallback, not a solution. |
| In-house code in voice apps | one public GitHub PR reads "dedh sau" / "saade teen sau" from Latin-spelled recogniser output and asks a follow-up when readings disagree, reporting silent wrong amounts 17.5% to 0% on 463 internal phrasings (self-reported) | **The best evidence of demand we found:** practitioners hit this and write it themselves. |
| LLM prompting | our own R12/R13 | Not enough on 3-4B models. Untested: 8-9B local and hosted models (their capability decides the market). |
| Voice-agent platforms | Sarvam, Gnani, Haptik (Jio), Yellow.ai, Skit.ai, Bolna, Caller Digital, Ozonetel, Acefone, Exotel, plus Vapi and Retell | Competitors **and** distribution partners. How they handle spoken values internally is unknown and may already be good. |

**The real gap (hypothesis):** an open, tested, Roman-and-Devanagari spoken-value layer that is
schema-aware, tense-aware, never invents a value, and abstains. Not yet proven absent: proprietary
platforms may already have it internally.

## Evidence update (2026-10-31)

Typed data now exists (RESULTS R16, R17): spoken-form number words are about 9% of card-driven messages, and
consented private chats (not published) suggest they are much rarer in real friend chat, where the common
problem is **ambiguity** (AM/PM, "kal" with no tense cue). The parsers flag that. This supports the
voice-first pitch: typed Hinglish would mostly be an abstention layer, while spoken input is where number
words appear.

## 3. Market and fit

- **Size (noisy, vendor-sourced):** India voice recognition about $0.4-0.6B in 2025; conversational
  AI about $0.57-0.65B; voice AI agents about $153M (2025) rising to about $957M by 2030 (a vendor
  estimate, unverified); Indian voice-AI start-ups raised over Rs 280 crore by early 2026. Definitions
  differ, so these do not add up.
- **Where spoken values hurt most:** BFSI (collections: commitment-to-pay amounts and dates, the
  highest-volume voice use case), e-commerce and logistics (delivery date, weight, COD amount),
  payments (UPI amounts, phone numbers), bookings. A wrong amount or date is a money or compliance
  event, not a quality blip. Collections vendors cite RBI data-localisation, which favours
  India-hosted or on-premise deployments (and so smaller local models), per vendor sources
  (unverified; check RBI circulars before saying it).
- **Who pays:** not an end customer buying "a normalizer". The realistic buyers are (1) voice-agent
  start-ups and platforms that want fewer wrong-value incidents, (2) BFSI/fintech/e-commerce teams
  building in-house on open models, (3) the open-source community (adoption, citations, credibility).
- **Fit verdict today: plausible, unproven.** What would prove it: (a) real transcripts showing
  spoken-form values in a meaningful share of requests *after* the ASR's own ITN; (b) bigger models
  failing too; (c) a design partner measuring fewer wrong-value incidents.

## 4. Product

**vaad-norm**, a small open-source (Apache-2.0) library and CLI, plus the existing gateway as a thin
deployment wrapper.
1. **Core parser:** numbers (Devanagari and Roman), fractions, lakh/crore, money, units, phones,
   times, relative dates with a tense/field resolver. Every output has a source span, a confidence
   and a reason; ambiguity returns `abstain` with a clarification, never a guess. Under 20 ms.
2. **Three integrations from one core (an ablation we run):** pre-annotate the user turn ("dedh kilo
   [=1.5 kg]"), post-verify tool arguments against the parsed candidates (repair or flag), or both.
3. **Voice middleware:** a Pipecat `FrameProcessor` and a LiveKit Agents component between STT and
   the LLM/tools, plus a **read-back guard** for high-risk values ("Rs 150000, confirm?").
4. **Benchmark and datasheet:** BFCL-Hinglish, value-heavy, the gold conversion set, and the
   independent held-out set (when it exists).
5. **Commercial surface (later, optional):** domain lexicon packs (BFSI, logistics, e-commerce),
   regression/eval service, integration support. The library stays free.

## 5. Voice: why it sells better, and how to do it

Voice sells better because spoken values are native there, errors are expensive and invisible, and
buyers already budget for voice agents. But the ASR layer is the product's biggest risk: Sarvam's
transcribe mode already returns digits for plain numbers.

Steps, in order:
1. **Test what ASR actually emits (the decisive experiment).** Record or synthesize ~300 utterances
   from the value-heavy templates, spoken by several native speakers, and run them through Sarvam
   Saaras v3 (transcribe, verbatim, codemix), Gnani Vachana, and Whisper. Count how often the
   *text reaching the LLM* still contains an unresolved spoken value. If a mainstream ASR resolves
   fractions, times and tense-dependent dates well, the voice pitch narrows to open-source/on-device
   ASR, verbatim-mode compliance logs, and the verification/abstention guarantee. If not, it is a
   strong pitch. Needs: a Sarvam key and 3-5 speakers.
2. **Make the speakers the independent test authors.** Native speakers who never saw our lexicons
   say each request in their own words; gold values come from them. This solves the shared-author
   problem and produces the voice benchmark in one go.
3. **Build the middleware** (Pipecat/LiveKit) and a **demo** whose failure is visible: a Hindi
   transfer or order where "dedh lakh" or "saade teen sau" executes wrongly without the layer and
   correctly or with a confirmation with it; show wrong-value rate, abstain rate, latency.
4. **Find 2-3 design partners** (small voice-agent start-ups, a fintech or logistics team): free
   integration for anonymized transcripts and a measured before/after.
5. **Compliance angle:** an audit trace per value (span, rule, confidence) is the thing a BFSI
   buyer can show a regulator; sell the trace, not just the accuracy.

## 6. Marketing (developer-led, honest)

- **Proof first:** one headline number from the held-out set and design-partner data, with the
  prompt (7-27%) and translate-first (7%) baselines next to it. Publish negatives too.
- **Assets (for the author to review before anything is published):** GitHub release; Hugging Face
  dataset and benchmark with datasheets; a 3-minute demo video; one blog post titled around the
  failure ("Your Hindi voice agent will wire the wrong amount"); an arXiv preprint (evaluation plus
  method).
- **Distribution:** `pipecat` and `livekit` plugins on PyPI (the way Gnani and Sarvam already
  publish theirs); Indic-NLP and voice-AI communities (AI4Bharat, Bhashini ecosystem, Indian
  developer forums); fintech and voice-AI meetups and conferences; direct outreach to the platform
  vendors as partners, not competitors.
- **Funding/credibility routes to check, not assume:** IndiaAI Mission and Bhashini ecosystem calls,
  AI4Bharat collaboration, Hugging Face and open-source grants. No specific open call was found.
- **Pricing:** none for the core. Credibility and partnerships first, services second.

## 7. Risks

1. ASR engines already normalize enough (test in 5.1).
2. Bigger models handle spoken values (test an 8-9B local model and one hosted model).
3. Real traffic rarely contains them, especially typed.
4. Our evidence is dev-only, 3-4B models, and an author-shared value-heavy set.
5. Platforms may already solve it privately.
6. A library is hard to monetize; the realistic outcomes are adoption, a paper, partnerships and
   services.

## Sources

Sarvam output modes (docs.sarvam.ai/.../select-output-mode); Sarvam Edge (sarvam.ai/blogs/sarvam-edge);
Sarvam ASR evaluation (sarvam.ai/blogs/evaluating-indian-language-asr); Smallest.ai ITN docs; Soniox ITN
wiki; DEV Community "Whisper transcribes spoken Hindi numbers as words" and github.com/Tushar-9802/hindi-normalize;
indic-punct (arXiv 2203.16825); NVIDIA NeMo-text-processing (github.com/NVIDIA/NeMo-text-processing) and
kenpath/indic-text-normalization; dateparser docs; vendor roundups (acefone, ozonetel, myoperator, bolna,
nimblebiz, caller.digital) for the platform list and Hinglish claims; IMARC and MarketsandMarkets India
voice/conversational AI pages and caller.digital for market sizes; The Ken (voice-AI funding); revrag,
ignosis, BootLabs, Oriserve and Haptik pages for BFSI use cases (vendor material); Gnani and Sarvam
LiveKit/Pipecat plugin pages; GitHub PR dmadan86/waves#1189 (voice amounts); IndiaAI, Bhashini and
AI4Bharat pages for ecosystem programmes.
