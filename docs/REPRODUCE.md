# Reproducing the results

## Environment used for every reported number

| Item | Value |
|---|---|
| Machine | Linux (Fedora, kernel 7.2.x), Intel i5-13420H, 15 GB RAM |
| GPU | NVIDIA RTX 3050 6 GB laptop (CUDA arch 86) |
| Inference | llama.cpp commit `df9beac` (`llama-server`, version 0.7.0-dev), built with CUDA, GCC 16.2 |
| Python | 3.12, managed with [uv](https://docs.astral.sh/uv/); dependencies pinned in `uv.lock` |
| Models | GGUF files listed with SHA-256 in `harness/models.yaml` |
| CI | GitHub Actions `ubuntu-latest`, llama.cpp release `b11860` (same commit) for the CPU smoke gate |

## 1. Code and checks

```sh
git clone https://github.com/Satyanshgaur/vaad && cd vaad
uv sync --locked
uv run ruff check . && uv run ruff format --check .      # gate 1
uv run mypy                                              # gate 2
uv run pytest tests/unit -m unit                         # gate 3
uv run pytest tests/integration -m integration           # gate 7
uv run python -m harness.leakage                         # gate 10
uv run python -m harness.split check harness/tasks --allow-missing test/
```

## 2. llama.cpp and models

```sh
git clone https://github.com/ggml-org/llama.cpp ~/tools/llama.cpp && cd ~/tools/llama.cpp
git checkout df9beac
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86 && cmake --build build -j
```

Download each GGUF named in `harness/models.yaml` from its `hf_repo` into `~/models/<name>/`
(`hf download <repo> <file> --local-dir ~/models/<name>`), then verify with `sha256sum`.
Serve one model: `scripts/llama_server.sh ~/models/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf 8080`
(`NGL=0` for CPU only; `CTX` sets the context, default 8192).

## 3. Task data

Dev tasks are in the repo (`harness/tasks/dev/`). The test split and the rewrite sources are in
the private repo and are needed only to rebuild or to run the test split:

```sh
scripts/private_sync.sh pull        # sources + test split from vaad-private (needs access)
```

To rebuild every task file from the pinned upstream revisions (and confirm the hashes match),
follow "Rebuilding" in `harness/tasks/README.md`. Changing any task needs a deliberate
re-lock: `split lock`, `leakage --write-hashes`, `private_sync.sh push`, and a note in the PR.

## 4. Baselines (R1-R3)

```sh
# one model at a time on port 8080
MODEL=qwen3.5-4b QUANT=Q4_K_M scripts/baseline_g0.sh     # raw twice + strong prompt
scripts/baseline_grid.sh                                  # other model/quant combinations
uv run python -m harness.run --tasks harness/tasks/dev --base-url http://127.0.0.1:8080 \
    --model qwen3.5-4b --quant Q4_K_M --no-think --seeds 4 5 6 7 --out harness/reports/<name>
```

Each run writes `results.jsonl` (one `TrialResult` per line), `summary.json` (metrics with 95%
CIs, by language) and `traces/responses.jsonl` (raw backend replies) under `--out`.
Defaults: temperature 0.7, seeds 0-3, `max_tokens` 512.

Paired comparisons between two runs: load both `results.jsonl`, compute per-task `pass^k`
with `harness.metrics.per_task_scores`, then `harness.metrics.paired_bootstrap_ci(treatment,
control)` on the same task order.

## 5. The gateway

```sh
cp config/vaad.example.yaml config/vaad.yaml      # edit backend URLs
uv run vaad serve --config config/vaad.yaml --port 8100
curl localhost:8100/v1/chat/completions -H 'content-type: application/json' -d '{...}'
```

Point any OpenAI-compatible client, or `harness.run --base-url http://127.0.0.1:8100`, at it.
Traces go to `trace_path`. Ablation switches are under `grammar:` in the config.

```sh
scripts/grammar_ablation.sh strict loose     # R7: dev through the gateway, both date grammars
```

## 6. Smoke gate (R5)

```sh
NGL=0 scripts/llama_server.sh ~/models/qwen3.5-0.8b/Qwen3.5-0.8B-Q8_0.gguf 8080 &
uv run python -m harness.smoke --base-url http://127.0.0.1:8080                  # check
uv run python -m harness.smoke --base-url http://127.0.0.1:8080 --write-baseline  # re-baseline
```

## Memory (long evals)

llama-server keeps a prompt cache in RAM, up to 8192 MiB by default. On the 15 GB machine used
here the Linux out-of-memory killer terminated llama-server twice during the follow-up runs
(2026-10-29, 17:24 and 18:03 IST). `scripts/llama_server.sh` now passes `--cache-ram 2048`
(`CACHE_RAM` overrides). **Which runs used which:** G0, g1-strict and the first part of g1-loose
used the 8192 MiB default; servers started after PR "cap prompt cache" (all `f1-*` runs and any
restart) use 2048. The cache only reuses identical prompt prefixes, so outputs for a fixed seed
should not change, but this has not been verified bit-for-bit. `harness.run --resume` and the
restart loop in `scripts/lib_resilient.sh` recover from a killed server.

## Determinism notes

- llama-server is deterministic for a fixed `seed`, model, build and hardware: re-running seeds
  0-3 reproduced every number. Different hardware or a different llama.cpp build may change
  individual trials, so compare reruns with the intervals, not exact values.
- The harness stores raw backend replies, so any score can be recomputed from `traces/` without
  the model.
- Task files, models and prompts are all hashed (`SPLITS.lock`, `harness/models.yaml`); a
  results file should always be read next to the commit that produced it.
