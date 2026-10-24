Hinglish Tool-Call Gateway: Design and Build Plan
24 Oct 2026 · @Satyansh
Summary
v1 is an open-source, OpenAI-compatible proxy that makes small local models produce correct tool calls from Hindi and Hinglish requests. It ships in about 8 weeks at 15–20 hours a week, and launches on one number: Hinglish pass^4 before versus after the gateway on the same 4-bit model.
Working name: sahi-call ("sahi" means correct). Rename freely.
• Who it's for: developers building Indian voice and chat agents on open models who can't afford frontier APIs on every turn, or who must keep data in India.
• What it does: validates and repairs tool-call arguments, normalizes Hinglish values (numbers, dates, amounts) into the format each tool expects, and routes hard turns to a stronger model.
• What makes it credible: a public reliability harness with multi-seed pass^k, run on every release.
The 8-week estimate assumes part-time work alongside college. If you have more time, phases compress but the gates stay the same.
Product scope
v1 is deliberately narrow: text in, tool calls out, three languages, one backend done well. Everything else waits until the launch number is real.
Primary user story: "I run a 3–4B model on one GPU for a Hinglish support bot. When a user says mera order kal tak bhej do, 2 kilo wala, the tool should get {"date": "2026-10-25", "weight_kg": 2}, not {"date": "kal"}."
Area
In v1
Out of v1 (later or never)
Languages
English, Hindi (Devanagari), Hinglish (Roman)
Other Indic languages (v2 candidates: Marathi, Bengali)
Input
Text chat turns
Speech, ASR errors
API
OpenAI /v1/chat/completions with tools, non-streaming
Streaming tool calls (v1.1), Anthropic-style API
Backends
llama.cpp llama-server (primary); any OpenAI-compatible URL as passthrough
vLLM-specific guided decoding, hosted service
Value types canonicalized
Integers and amounts, currency (₹, rupaye, lakh, crore), dates and relative days, times, phone numbers, units (kg, litre)
Addresses, free-text names (passed through, never altered)
Repair
Schema validation, one guided retry, flag-instead-of-execute
Multi-step planning repair
Routing
Two tiers (small 4-bit / stronger model) by language and turn difficulty
Learned router, cost optimization across providers
Deliverables
pip package, Docker image, eval harness, 2–3 Indic-calibrated GGUF quants with reliability cards, demo video
UI dashboard, SaaS
Success metrics for v1 launch
Metric
Target
Why
Hinglish tool-call pass^4, 4-bit 3–4B model, with vs without gateway
Gain of at least 10 points
The launch claim; set after the Week 1 baseline
English pass^4 with gateway
No drop beyond noise (95% interval overlaps)
Proves it doesn't harm the easy case
Wrong-value execution rate
Lower than baseline; flagged instead
Safety: a wrong amount is worse than a question back
Added latency (p50, canonicalizer only)
Under 20 ms per call
Must be invisible next to model latency
Tests
All PR gates green; 200+ canonicalizer unit cases
Trust for outside users
The 10-point target is a placeholder. Fix it after measuring the baseline in Week 1, and don't move it after seeing results.
Architecture
The gateway is a pipeline of four stages around the model call. Its key behaviour: an uncertain value is never silently executed; it is retried once or returned to the user as a question.
A request enters on the left, is routed and has its schema tightened, goes to the model, and comes back through validation and canonicalization. The confidence check then executes, retries once, or asks back. Every stage logs a trace that the harness reads.
Components in detail
Six components, each behind a small interface so it can be tested and benchmarked alone. The canonicalizer is the novel part; the others mostly wire existing capabilities together well.
1. API proxy (server/)
• FastAPI app exposing /v1/chat/completions and /v1/models, OpenAI-compatible so existing agents only change base_url.
• Runs the pipeline: detect language → route → call backend → validate → canonicalize → decide (pass, repair, or flag).
• Every request writes one structured trace (JSON lines): language, route, raw arguments, canonicalized arguments, decision, latency per stage. Traces feed the harness and debugging.
• Config in one YAML file: backends, routing thresholds, per-tool canonicalization overrides.
2. Language detector and router (router/)
• Language ID: script check (Devanagari vs Latin) plus a small Hinglish word list scored per turn. Output: en, hi, hinglish, with a confidence. Deterministic and well under 1 ms.
• Difficulty signals: number of tools offered, whether the turn needs several calls, presence of numbers or dates in the user turn.
• Policy (v1, rules not learning): Hinglish or Hindi plus any difficulty signal → strong tier; otherwise → small tier. Thresholds live in config and are tuned on the dev set only.
• Tiers on your laptop: small tier = 4-bit 3–4B model in llama-server; strong tier = 8-bit of the same model on Kaggle during eval, or any OpenAI-compatible URL. Two models won't comfortably share 6GB.
3. Constrained decoding layer (grammar/)
• llama-server converts a JSON Schema into a grammar per request and zeroes out tokens that would break it (Liquid AI llama.cpp docs). Tool calling needs --jinja (function calling docs).
• The gateway tightens schemas before sending them: typed fields get pattern, enum and maxLength; dates become an ISO pattern; numbers stay numbers. Unsupported schema keywords are silently ignored, so the gateway validates again after generation.
• Design choice to test: strict grammar on dates can force a confident wrong date. The alternative is a loose grammar plus canonicalization. The harness decides which wins per field type.
4. Argument canonicalizer (canon/), the core
A deterministic, schema-aware normalizer. It never invents values; it converts or flags.
Value type
Examples handled
Output
Numbers
"nau sau", "नौ सौ", "dedh", "dhai", "2.5k"
900, 900, 1.5, 2.5, 2500
Indian money units
"5 lakh", "ढाई करोड़", "Rs 500", "500 rupaye"
500000, 25000000, 500, 500
Relative dates
"aaj", "kal", "parson", "agle somvaar"
ISO date from a reference date
Times
"shaam 5 baje", "subah saade nau"
17:00, 09:30
Phone and IDs
spoken digits, "double nine"
digit string, checked by length
Units
"2 kilo", "aadha litre"
number in the schema's unit
• The hard case is "kal": it means both yesterday and tomorrow. Resolve it from verb tense in the turn ("bhej do" future, "aaya tha" past) and from the tool's semantics (a delivery date is future). If ambiguity remains, flag instead of guessing. This is a genuine research question worth its own short write-up.
• Libraries: dateparser lists Hindi support (BSD-3) and covers Devanagari dates; use it as a fallback, not the core. For Devanagari, reuse NVIDIA NeMo's Hindi inverse text normalization (ITN), which turns spoken-form Hindi numbers into digits (NeMo docs); Gnani's speech API does similar Hindi ITN for currency, times and phones (Gnani docs). What I didn't find: ITN for Romanized Hinglish, relative-date resolution, or normalization tied to a tool's schema with confidence. Build those; that is where your value is.
• Confidence and decisions: each conversion returns a value and a confidence. High → pass; medium → one guided retry with the error in the prompt; low → return a clarification flag to the agent instead of executing.
• Never touch: free-text fields (names, addresses, messages). The schema decides what is safe to normalize.
5. Reliability harness (harness/)
• Runs a task set N times per condition and reports pass@1, pass^k, schema-validity, wrong-value execution rate and latency, with bootstrap 95% intervals.
• Conditions are a grid: model × quant level × language × gateway on/off × seed.
• Same harness runs locally, on Kaggle, and in CI (a small smoke subset on a tiny model).
6. Indic quants (quants/)
• A script that builds GGUF quants with an importance matrix computed on Hindi and Hinglish text, then runs the harness and writes a reliability card for the Hugging Face model page.
• v1 ships 2–3 small models, each with a standard-calibrated and an Indic-calibrated quant, so the comparison is on the page.
Tech stack and repo layout
Python for everything in v1, because the gateway's cost is model latency, not proxy speed. Rust is an optional later port of the canonicalizer if profiling ever shows it matters.
Layer
Choice
Reason
Language
Python 3.11+
Fast iteration; matches your existing projects
API server
FastAPI + Uvicorn, httpx for backend calls
OpenAI-compatible endpoints in a few hundred lines
Schemas and validation
Pydantic v2, jsonschema
Validate tool arguments against the agent's own schemas
Inference backend
llama.cpp llama-server with --jinja
Runs on your RTX 3050; native tool calling and JSON-schema grammars
Date fallback
dateparser
Lists Hindi support; BSD-3 license
Tests
pytest, hypothesis (property tests), pytest-benchmark
Canonicalizer needs hundreds of cases plus fuzzing
Lint and types
ruff, mypy --strict on canon/ and router/
Catches the bugs that silently change values
Packaging
uv, pyproject.toml, Docker image
One-command install for users
CI
GitHub Actions
Free for public repos
Experiment tracking
JSON-lines traces + a results CSV committed per release
Reviewable in PRs; no paid service
sahi-call/
├── src/sahi_call/
│   ├── server/        # FastAPI app, OpenAI-compatible routes, tracing
│   ├── router/        # language ID, difficulty signals, routing policy
│   ├── grammar/       # schema tightening, post-generation validation
│   ├── canon/         # numbers, money, dates, times, phones, units
│   │   └── lexicons/  # Hindi + Hinglish word lists (YAML, reviewed)
│   └── config.py
├── harness/           # task sets, runners, metrics, bootstrap CIs
│   ├── tasks/         # dev / test splits, never mixed
│   └── reports/       # committed results per release
├── quants/            # imatrix calibration text, build + card scripts
├── tests/             # unit, property, golden, integration
├── examples/          # a Hinglish order-tracking agent demo
├── docs/
└── .github/workflows/ # CI gates (see PR gates)
Evaluation plan
The launch evaluation is about 24,000 model calls, roughly 20 GPU-hours at an assumed 3 seconds per call. That's about 540 test instances × 2 models × 2 quants × gateway on/off × 4 seeds, plus ablations on one model. It fits a week of overnight runs on your laptop, or Kaggle. Time one call in Week 1 and redo this budget.
Task sets
Set
Source
Size (planned)
Role
BFCL-Hi
NVIDIA, CC-BY-4.0: simple, multiple, parallel, relevance categories
~150 tasks sampled
Hindi baseline, comparable to published work; the original English BFCL tasks give the English condition
BFCL-Hinglish
Romanized and code-mixed rewrites of the same tasks, hand-checked
~150 tasks
Your new contribution; same tasks enable a paired comparison
Value-heavy set
Written by you: Indian e-commerce, banking, delivery, booking tools where arguments are amounts, dates, phones
~150 tasks × 3 languages
Where the canonicalizer should matter most
Read the BFCL-Hi files directly as JSON; the dataset card warns against loading it with the datasets library.
Rules that keep results honest
• Split every set into dev (40%) and test (60%) on day one. Tune lexicons and router thresholds on dev only. Touch test once per release.
• Seeds: 4 trials per task per condition, temperature 0.7, so pass^4 is measurable. Also report temperature-0 pass@1 as a sanity check.
• Report bootstrap 95% intervals. Call a gain real only when intervals don't overlap.
• Freeze the model versions, quant files (by hash) and prompts in the results file.
Grid for the launch result
• Models: 2 small instruction models with native tool calling (pick in Week 1 from what runs on 6GB, for example a 3–4B and a 1.5–2B).
• Quant: Q8_0 vs Q4_K_M (plus Indic-calibrated Q4 in Phase 3).
• Languages: English, Hindi, Hinglish.
• Gateway: off vs on, plus ablations (grammar only, canonicalizer only, router only).
Metrics
• pass@1 and pass^4 on full tool-call correctness (function name + all arguments).
• Schema-valid rate.
• Wrong-value execution rate: a call executed with a plausible but wrong value. This is the metric that matters to a business.
• Flag rate: how often the gateway asks instead of executing. Too high means it's useless.
• Latency added per stage (p50, p95).
Baselines to beat: the raw model; the raw model with a strong system prompt telling it to use English and ISO formats; and one guided retry without canonicalization. Beating only the raw model isn't a convincing claim.
Timeline
About 8 weeks part-time, about 130 hours in total by my estimate. The canonicalizer gets the most time because it carries the launch claim.
Phase
Weeks
Main work
Hours (est.)
0 Setup and baseline
1
Repo, CI skeleton, pick models, build harness, write Hinglish and value-heavy task sets, freeze splits, raw baseline
18
1 Proxy, grammar, CI
2–3
FastAPI proxy, tracing, schema tightening, validator, guided retry, PR gates 1–9
30
2 Canonicalizer
4–5
Lexicons, number and money parser, dates and "kal" resolver, times, phones, units, confidence, 300+ golden cases
35
3 Router and quants
6
Language ID, routing rules, Indic imatrix quants, reliability cards
17
4 Test run, docs, demo
7
One-time test run, ablations, README, Docker, demo agent and video
17
5 Launch
8
Write-up, posts, emails, Hugging Face release, issue triage
13
Gates G0–G4 are defined under PR gates. A missed gate moves every later date; it doesn't skip the gate.
PR gates
Two kinds of gate: PR gates run automatically on every pull request, and milestone gates are the exit criteria for each phase. Work alone with PRs anyway; the history becomes evidence of engineering discipline that reviewers and professors can read.
Every PR (GitHub Actions, must be green to merge)
#
Gate
Check
Fails when
1
Lint and format
ruff check, ruff format --check
Any error
2
Types
mypy --strict on canon/, router/, grammar/
Any error
3
Unit tests
pytest tests/unit
Any failure; coverage of canon/ below 90%
4
Golden canonicalization
Fixed YAML file of input → expected value pairs (starts ~200, grows every PR that touches canon/)
Any case changes output
5
Property tests
hypothesis: number-word round trips, never altering free-text fields, idempotence (canonicalizing twice = once)
Any counterexample
6
No value invention
Every output value must trace to a span in the user turn or a reference date
A value without a source span
7
Proxy contract
Integration test with a mocked backend: OpenAI response shape, passthrough parity with gateway disabled
Shape differs or passthrough changes anything
8
Latency budget
pytest-benchmark on 1,000 canonicalizations
p95 above 20 ms or 25% slower than main
9
Smoke eval
50 dev tasks on a tiny model on the CI runner's CPU, 1 seed
Schema-valid rate drops versus the stored baseline
10
Leakage guard
Script checks no test-split task text appears in lexicons, prompts or tests
Any overlap
Gate 9 is a regression alarm, not a quality claim; a tiny CPU model is noisy. Pick the smallest tool-calling model that runs on the free runner in Week 1.
PR conventions: one change per PR; title in conventional-commit form (feat(canon): parse lakh/crore); description lists what changed, golden cases added, and the smoke-eval delta. PRs touching canon/lexicons/ need a short note on where the words came from.
Release PRs (to main with a version tag)
• Full dev-set eval on Kaggle or locally, 4 seeds, results CSV committed to harness/reports/.
• No metric worse than the previous release beyond its 95% interval.
• CHANGELOG entry and updated reliability numbers in the README.
Milestone exit gates
Gate
End of
Pass criteria
G0 Baseline
Week 1
Harness reproduces the same raw-model numbers twice (within interval); dev/test split frozen; launch target written down
G1 Safe proxy
Week 3
Gateway-off passthrough identical to raw; schema-valid rate ≥ 99% with grammar on; gates 1–9 live in CI
G2 Canonicalizer works
Week 5
Hinglish dev pass^4 up with non-overlapping interval; English not worse; wrong-value execution rate down; 300+ golden cases
G3 Routing and quants
Week 6
Router beats both single tiers on accuracy per unit latency on dev; Indic-calibrated quant compared to standard on dev
G4 Launch ready
Week 7
One-time test-split run done; README with results, quickstart under 5 minutes, Docker image, demo video, write-up drafted
If a gate fails, fix or cut scope before moving on. Never re-run the test split to chase a number.
Release artifacts
v1 can ship ten public artifacts from one body of work. Each is a separate entry point: an engineer finds the package, a researcher finds the dataset, a Kaggle user finds the notebook, and each links back to the others.
#
Artifact
Where
Ships in
Who uses it
License
1
sahi-call gateway code
GitHub
Phase 1 onward
Agent developers
Apache-2.0
2
Python package + Docker image
PyPI, GitHub Container Registry
Phase 4
Anyone running llama.cpp
Apache-2.0
3
BFCL-Hinglish: Romanized, code-mixed versions of BFCL-Hi tasks, paired with the originals
Hugging Face Datasets, mirrored on Kaggle Datasets
Phase 0–2
Researchers comparing languages
CC-BY-4.0 (BFCL-Hi is CC-BY-4.0; keep the attribution)
4
Indic value-heavy tool-call set: e-commerce, banking, delivery, booking tasks in 3 languages
Hugging Face, Kaggle
Phase 0–2
Agent evaluation
CC-BY-4.0
5
Hinglish canonicalization gold set: input span → typed value, with "kal"-style ambiguity labels
Hugging Face, Kaggle
Phase 2
ITN and normalization researchers; useful even without the gateway
CC-BY-4.0
6
Indic-calibrated GGUF quants (2–3 models) with reliability cards
Hugging Face Models
Phase 3
Local-LLM users
Base model's license
7
Calibration text + quant recipe script
GitHub quants/
Phase 3
People quantizing other models
Apache-2.0 / source licenses
8
Kaggle notebooks: (a) reproduce the baseline on free T4s, (b) run the gateway on your own tools, (c) build an Indic quant
Kaggle Code
Phases 1, 3, 4
Students and practitioners; Kaggle rewards these with visibility
Apache-2.0
9
Results: raw traces, results CSVs, harness reports per release
GitHub harness/reports/, Hugging Face dataset
Every release
Reviewers checking claims
CC-BY-4.0
10
Write-up: blog post + arXiv preprint
Your site, arXiv
Phase 5
Professors, recruiters, X
—
Optional: a Hugging Face Space demo running a 1.5B model on the free CPU tier. It'll be slow, so treat it as a toy, and decide after timing it.
Release standards that make artifacts citable
• Every dataset gets a datasheet: how it was built, who checked it, splits, known limits, intended and unintended use.
• Every model gets a card with the reliability numbers, the test-split hash and the harness version.
• Pin versions and give each release a DOI through Zenodo's GitHub integration, so papers can cite an exact version.
• Keep the test split private-but-hashed until the paper is out, or release it with a canary string, so models can't quietly train on it. Decide this before Phase 2.
Licensing check before release: BFCL-Hi is CC-BY-4.0 per its card. Confirm the original BFCL license on the Gorilla repo before releasing derived English tasks, and confirm each base model's license allows redistributing quants.
Research contribution
Yes, this can be a real paper, if the baseline shows a meaningful Hinglish gap. The contribution is the dataset plus the measured finding plus the method together, not any one artifact. Kaggle notebooks and Hugging Face models are how people find and reproduce the work; they don't count as the contribution on their own.
The four claims, strongest first
#
Claim
Type
What makes it new (based on my searches)
Evidence needed
C1
Compression hurts Hindi/Hinglish tool-call reliability (pass^k, wrong-value execution) more than English
Measurement
Prior work measured multilingual tool calling at full precision (Luo et al.) or quantization in translation (Marie & Fujita), not the two together with repeated trials
Grid with intervals; 2+ model families
C2
Schema-aware, confidence-gated canonicalization recovers most of that gap, beating prompting, grammar alone and blind retry
Method
Luo et al. found inference-time fixes don't reach English level; you test a different fix: deterministic normalization tied to the schema
Ablations; results on the held-out test split only
C3
BFCL-Hinglish, the value-heavy set and the canonicalization gold set
Resource
Paired Hinglish versions of an existing benchmark let you compare languages on identical tasks; Devanagari ITN exists, Romanized Hinglish ITN data didn't turn up
Datasheet; native-speaker agreement on a sample
C4
Analyses: when grammar constraints hurt; how "kal" ambiguity is resolved; whether Indic calibration helps tool calls
Findings
Small, concrete, quotable results
Per-field-type breakdowns
The "new" column reflects what I could find, not a full literature review. Before writing, run a focused search (next subsection) and position against the closest work: Lost in Execution, BFCL-Hi, KiranaBench, hinglish-caller-bench, QuantClaw and NeMo Hindi ITN.
Possible title: Lost in Normalization: Making Small Compressed Models Reliable at Hinglish Tool Calling.
Where to look before claiming novelty
1. ACL Anthology and arXiv cs.CL: search "code-mixed function calling", "Hinglish tool use", "inverse text normalization Hinglish", "quantization tool calling", last 18 months.
2. Semantic Scholar: open the closest papers above and read everything that cites them. Set alerts on them.
3. Hugging Face Datasets: search "Hinglish", "function calling Hindi", "BFCL" for existing datasets you'd duplicate.
4. GitHub: search "hinglish tool call", "hindi ITN", "indic normalization" for existing code.
5. Ask: once you email authors after G2, ask whether they know of overlapping work. Researchers usually do.
Venues
Venue
Deadline
Fit
Notes
ACL 2027 via ACL Rolling Review
Jan 4, 2027 (AI Weekly)
Main or short paper on C1 + C2 + C3
Conference Aug 20–22, 2027. Only 3 weeks after the Dec 15 launch, so aim for a 4-page short paper or use a later cycle
ACL 2027 workshops (held Aug 18–19, 2027)
Usually spring; not announced yet
Low-resource or code-switching workshops
LoResLM published Hinglish work in 2026; check which workshops ACL 2027 accepts
NeurIPS 2027 Evaluations & Datasets track
Not announced; in recent years around May
C1 + C3 as an evaluation paper
The 2026 track explicitly welcomes evaluation methodology, datasets and negative results (NeurIPS blog)
arXiv preprint
Right after launch
Everything
Timestamps your claim; send this link in professor emails
Indian venues such as ICON are good for networking with Indic NLP groups; check their 2026–27 dates directly.
Recommendation: post the arXiv preprint at launch, then submit the polished version to the NeurIPS 2027 Evaluations & Datasets track or an ACL 2027 workshop. A professor who replies after G2 may become a co-author, which helps both the paper's quality and its chances.
Future scope
The eventual goal is to become the default open reliability layer and benchmark for agents in Indian languages: what developers install when a small model talks to tools in Hindi, Marathi or Tamil, and the leaderboard papers report against. v1 proves the idea on one language pair; each later phase widens it only after outside people use the previous one.
Dates past v1 are rough and depend on the gates, which are suggestions. Change them if a different signal of real use appears first.
What each phase adds, and why it's next
• v1.x Hardening (Jan–Mar 2027). Streaming tool calls, a vLLM backend, and more value types (addresses with PIN codes, account numbers). Community-contributed lexicons with review. Paper submission. Why next: first users will hit these walls immediately.
• v2 More of India (Apr–Jun 2027). Marathi, Bengali, Tamil and Telugu, plus their English code-mixed forms. Speech input: tool calls from ASR transcripts with recognition errors, since voice agents are the biggest Indian use case. A public Indic agent reliability leaderboard comparing models and quant levels on pass^k. Why next: the leaderboard turns the dataset into a standard other people report against, the strongest form of research traction.
• v3 In the model (Jul–Dec 2027). Use gateway traces and the gold set to QLoRA fine-tune 1.5–3B "tool-call specialist" models on Kaggle that need less correction. Replace rule routing with a small learned router. Run on Android through llama.cpp. Why next: the gateway then becomes training-data infrastructure, not only a patch.
The two end states (you don't have to pick yet)
Path
What it looks like
What you'd need by then
Research
A line of 2–3 papers (measurement, method, multilingual leaderboard) that forms a coherent grad-school application or thesis topic: reliable agents under compression in low-resource languages
A professor collaborator; the leaderboard adopted by others
Product
An on-prem, DPDP-friendly gateway with support and integrations, sold to Indian voice-agent and fintech companies running open models
Real users from v1–v2; at least one company piloting it
The two paths share the same core artifacts until v2, so the decision can wait until the gates tell you which one has pull.
Explicitly not the goal: training a large foundation model, competing with Sarvam or AI4Bharat on base models, or building a general agent framework. The project stays the reliability layer around models.
Risks and fallbacks
The biggest risk is a small gain: if base models already handle Hinglish values well, the launch number is weak. Week 1's baseline exposes this early, before you've built much.
Risk
Early sign
Fallback
Baseline already good; small gain
G0 shows Hinglish pass^4 close to English
Shift the claim to 4-bit and smaller models, where damage is larger; or lead with wrong-value execution rate
Canonicalizer makes confident errors
Golden cases pass but dev wrong-value rate rises
Raise confidence thresholds; flag more; narrow to the 3 value types that work
"kal" ambiguity unsolved
Many flags on date tasks
Ship flagging for ambiguous dates; turn the analysis into a short paper
Grammar constraints hurt accuracy
Grammar-only ablation worse than raw
Use loose grammar plus canonicalization; publish the finding
Hinglish task set seen as artificial
Reviewers question rewrites
Have 2–3 native speakers check a sample; report agreement; include real-style messages
6GB GPU too slow for the grid
Week 1 timing over ~6 s per call
Cut to 1 model at full grid; run the second on Kaggle
Frontier APIs make this moot
—
Positioning is open small models on cheap hardware, where the problem persists
Scope creep (streaming, more languages)
Phase dates slipping
Out-of-scope table is the contract; log ideas as GitHub issues for v2
Open questions
[ ] Which two base models? Decide in Week 1 from what supports native tool calling in llama.cpp and fits 6GB at Q8.
[ ] Final project name and license (Apache-2.0 suggested, so companies can adopt it).
[ ] Who are 2–3 native Hinglish speakers who can check a task sample?
[ ] Strong tier for the demo: local 8-bit on Kaggle, or a hosted Indic model API?
Sources
• llama.cpp structured output (Liquid AI docs)
• llama.cpp function calling (Liquid AI docs)
• BFCL-Hi dataset card
• Benchmarking Hindi LLMs (BFCL-Hi paper)
• dateparser
• indic-num2words
• Lost in Execution: multilingual tool calling (ACL 2026)
• hinglish-caller-bench
• QuantClaw: precision routing by task
• Research background: Research Landscape doc
Added for artifacts, research and roadmap:
• NeMo text (inverse) normalization, language support
• Gnani speech-to-text ITN
• The Uneven Impact of Post-Training Quantization in MT
• KiranaBench
• ACL 2027 submissions (AI Weekly)
• NeurIPS 2026 Evaluations & Datasets track
