# Architecture and behaviour of the gateway

What is built (Phase 1) and what is still a stub. Source: `src/vaad/`.

## Request flow

```
client --> /v1/chat/completions --> [tighten tool schemas] --> backend (llama-server)
                                                                  |
client <-- reply, or vaad_flag clarification <-- [validate] <-----+
                                      \--> one guided retry on invalid calls
```

Planned stages not yet built: language ID and routing (Phase 3), canonicalization and
confidence-based decisions (Phase 2). The trace fields for them exist and are empty.

## Modes

- **`gateway_enabled: false`:** a byte-faithful passthrough. The request body goes to the
  backend as received, the reply (status, body bytes, content type) comes back untouched, and
  `stream: true` streams through. No trace is written. Tested by gate 7.
- **`gateway_enabled: true`:**
  - A request with `tools` (and `tool_choice` not `none`) goes through the pipeline below.
  - A request without tools is forwarded as received and only traced.
  - `stream: true` is refused with HTTP 400 (`streaming_unsupported`).
  - Text answers and non-200 backend replies pass straight through, with no retry.

## Pipeline for tool requests (`server/pipeline.py`)

1. **Tighten** every tool's `parameters` (`grammar/tighten.py`) and send those copies. The
   client's original schemas are kept for validation.
2. **Call** the backend.
3. **Validate** each returned call against the *original* schemas (`grammar/validate.py`):
   unknown tool name, arguments not valid JSON, arguments not an object, schema errors. A
   backend 500 that means "could not parse the model's tool-call text" counts as invalid.
4. **Decision**
   - no errors: `pass`, the backend's reply is returned unchanged;
   - errors and `retry` on: **one retry** with a note appended as a *user* turn (so every
     chat template accepts it) naming the rejected call and the problems and asking for a
     corrected call that keeps quoted text and does not guess values;
   - still invalid, or `retry` off: `flag`.
5. **Flag response:** HTTP 200, an assistant message with clarification text and no
   `tool_calls`, `finish_reason: "stop"`, and a `vaad_flag` object inside the message:

```json
{"reason": "invalid_arguments", "tool": "ship_order", "errors": ["ship_order: ..."], "attempts": 2}
```

Response headers: `x-request-id` always; `x-vaad-decision: pass|flag` when a tool call was judged.

## Schema tightening rules (`grammar/tighten.py`)

Conservative by design: a constraint is added only when the field's own description makes it
unambiguous, and an existing `enum`, `const`, `pattern` or `format` is never replaced.

| Trigger in the description | Added |
|---|---|
| contains `YYYY-MM-DD` (and not `HH`) | ISO date pattern (month 01-12, day 01-31) |
| contains `HH:MM` (and not `YYYY-MM-DD`) | 24-hour time pattern |
| contains `10-digit` / `10 digit` | `^[0-9]{10}$` |
| "either / one of / must be / valid values are" followed by 2+ quoted values, no "e.g." / "for example" / "such as" | `enum` of those values (`infer_enums`) |
| any other unconstrained string | `maxLength` (default 512; 0 disables) |

Also dropped from what is sent: keywords llama.cpp does not implement (`uniqueItems`,
`multipleOf`, `not`, `if/then/else`, `contains`, `propertyNames`, `minProperties`,
`exclusiveMinimum/Maximum`, `dependent*`, `unevaluated*`, `$comment`). They would be ignored
anyway; validation after generation still enforces them. Numbers stay numbers; `type` and
`required` are never touched. Patterns use `[0-9]` instead of `\d`.

**Known behaviour (the reason for the strict-vs-loose ablation):** a strict date grammar
guarantees a *well-formed* date, not a *right* one. On a real 0.8B model, "kal tak bhej do"
with today = 2026-10-24 produced `2026-10-24`: valid, confident, wrong.

## Configuration (`config/vaad.example.yaml`)

```yaml
gateway_enabled: true
small:  {url: http://127.0.0.1:8080, model: small-q4, api_key: null, timeout_s: 120}
strong: {url: http://127.0.0.1:8081, model: strong-q8}     # unused until the router exists
routing: {min_tools_for_strong: 4, strong_on_indic_with_values: true}   # Phase 3
thresholds: {pass: 0.9, retry: 0.6}                        # canonicalizer, Phase 2
grammar:
  enabled: true            # false sends the client's tools untouched (still validates/retries)
  date_grammar: strict     # strict | loose   (ablation switch)
  infer_enums: true
  max_length: 512
  retry: true              # false: flag on the first invalid call
canon:
  mode: off              # off | annotate | verify | both (docs/PREREG.md A5)
  ref_date: null         # today when null; fixed in evaluations
  ungrounded: ignore     # ignore | flag a typed value with no support in the turn
trace_path: traces/vaad.jsonl
overrides: {}              # per-tool value-type overrides, Phase 2
```

Auth: a configured `api_key` is sent to the backend; otherwise the caller's `Authorization`
header is forwarded.

## Errors

| Situation | Response |
|---|---|
| no backend configured | 503 `no_backend` |
| body is not valid JSON / not an object | 400 `invalid_json` / `invalid_request` |
| backend unreachable | 502 `backend_unreachable` |
| backend timeout | 504 `backend_timeout` |
| backend answers with an HTTP error | passed through unchanged |

All gateway errors use the OpenAI shape: `{"error": {"message", "type": "vaad_error", "code"}}`.

## Trace (one JSON line per request when enabled)

```
request_id, lang, lang_confidence, tier, raw_args, canon_args, decision, retried,
status, error, stage_ms {backend, validate, total}
```

With `canon.mode` on, the trace also carries an **audit trail**: `canon_version` (package version plus a
fingerprint of the lexicons) and, in `canon_args`, one record per checked tool argument: tool, argument, parser
kind, status (agree / repair / ambiguous / ungrounded), the model's value and the final value, confidence, the rule
that decided, and the character span in the user's turn. Offsets only: the user's words are never stored, and
phone numbers are masked to their last two digits. `raw_args` is the first attempt's calls as `{name, arguments}`; malformed arguments stay as the
raw string. `lang`, `canon_args` and (for non-tool requests) `decision` are empty for now.
The harness reads these files for per-stage analysis.

## Module status

| Module | Status |
|---|---|
| `server/` (app, backend, routes, pipeline, tracing) | built, gate 7 |
| `grammar/` (tighten, validate) | built |
| `canon/numbers.py`, `money.py`, `lexicon.py` | built (2026-10-31): number words (Roman and Devanagari), fractions, lakh/crore, `k`/`cr`, digits, rupee amounts; identifiers such as `OD4821` are never read as quantities; `find_numbers` returns spans and confidences |
| `canon/times.py`, `dates.py`, `tokens.py`, `lexicon_time.py` | built (2026-10-31): clock times with am/pm and part-of-day resolution, colloquial fractions (saade nau baje), 24-hour notation, durations; dates (today, kal/parson with tense and field direction, weekdays, day-month, N days later, tarikh); ambiguous results carry low confidence and both readings |
| `canon/` units, phones | stubs, Phase 2; `decide.py` (confidence to pass/retry/flag) exists |
| `router/` (langid, difficulty, policy) | stubs, Phase 3 |
| `quants/` | Phase 3 |

## CI gates

| Gate | What | Status |
|---|---|---|
| 1 | ruff lint and format | live |
| 2 | mypy (strict on canon/, router/, grammar/) | live |
| 3 | unit tests | live |
| 4 | golden canonicalization cases (`tests/golden`, 237 so far) | live (numbers, money, times, dates, durations) |
| 5 | property tests (hypothesis): spoken round trip, digits, free text untouched, time/date round trips | live (numbers, times, dates) |
| 6 | no value invention (every output traces to a span or the reference date) | live (numbers, times, dates: spans in range, ordered, no match without date/time words) |
| 7 | proxy contract with a mocked backend (`tests/integration`) | live |
| 8 | latency budget (p95 < 20 ms per 1,000 canonicalizations) | Phase 2 |
| 9 | smoke eval, 0.8B on CPU (`smoke.yml`) | live (about 5 minutes on GitHub) |
| 10 | leakage guard (6-gram hashes of the test split) | live |
| split lock | `SPLITS.lock` unchanged | live |
