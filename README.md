# vaad

An open-source, OpenAI-compatible gateway that makes small local models produce correct tool
calls from Hindi and Hinglish requests.

> User: *mera order kal tak bhej do, 2 kilo wala*
> Without vaad: `{"date": "kal"}` · With vaad: `{"date": "2026-10-25", "weight_kg": 2}`

vaad sits between your agent and `llama-server` (or any OpenAI-compatible backend). It routes
each turn to a small or strong model, tightens tool schemas, validates the arguments that come
back, and canonicalizes Hinglish values (numbers, lakh/crore, relative dates, times, phones,
units) into the format each tool expects. An uncertain value is never silently executed: it is
retried once or returned to the user as a question.

**Status:** pre-alpha, Phase 0 (setup and baseline). Nothing here works end to end yet.
See [docs/PLAN.md](docs/PLAN.md) for the roadmap and [docs/brief.md](docs/brief.md) for the
design.

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
