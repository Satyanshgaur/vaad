# vaad

A deterministic layer that grounds Hindi and Hinglish spoken values for small local models: numbers
("dedh hazaar" = 1500), money (lakh, crore), quantities, clock times ("saade aath baje"), durations,
phone numbers and relative dates ("kal" resolved from tense and the field). It gives each value a span and a
calibrated confidence, and **asks instead of guessing** when the text is ambiguous (AM or PM, an unmarked
"kal"). It can run as a library or as an OpenAI-compatible gateway in front of `llama-server`.

```python
from datetime import date
from vaad.canon import annotate_turn

annotate_turn("mera order kal tak bhej do, dedh hazaar rupaye", date(2026, 10, 24))
# 'mera order kal [=2026-10-25] tak bhej do, dedh hazaar [=1500] rupaye'
```

**What is measured** (details and caveats in [docs/RESULTS.md](docs/RESULTS.md), calibration in
[docs/CALIBRATION.md](docs/CALIBRATION.md)):

- On 189 held-out human-typed tool-calling tasks, the normalizer raised pass^4 by 16 to 22 points on three
  small models (all intervals above 0) and cut wrong values from 23-42% to 7-9% with `canon.mode: both`.
- Outputs the parser is at least 90% sure of were right 97-100% of the time on held-out data.
- These tasks were written to contain values. In real chat such values are rare, and spoken input through
  ASR is **not tested yet** (planned for v2, see [docs/AUDIO_SPEC.md](docs/AUDIO_SPEC.md)).
- Lexicons are AI-written and not yet native-reviewed.

**Status:** pre-alpha. See [docs/](docs/README.md) for the plan, results, methods, data, architecture and
decisions.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest                     # tests
uv run ruff check . && uv run ruff format --check .
uv run mypy                       # strict on canon/, router/, grammar/
uv run python -m harness.leakage  # gate 10
uv run vaad serve --config config/vaad.yaml   # copy from config/vaad.example.yaml
```

## Layout

| Path | What |
|---|---|
| `src/vaad/server/` | FastAPI proxy, OpenAI-compatible routes, tracing |
| `src/vaad/router/` | language ID, difficulty signals, routing policy |
| `src/vaad/grammar/` | schema tightening, post-generation validation |
| `src/vaad/canon/` | the canonicalizer: numbers, money, dates, times, phones, units |
| `harness/` | task sets, runner, metrics, bootstrap intervals, reports |
| `quants/` | Indic-calibrated GGUF quant recipes and reliability cards |
| `tests/` | unit, golden, property and integration tests |

## License

Apache-2.0.
