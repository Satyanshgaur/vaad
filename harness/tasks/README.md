# Task sets

| Set | Source | Planned size |
|---|---|---|
| `bfcl_hi` | NVIDIA BFCL-Hi (CC-BY-4.0), read as raw JSON, not via `datasets` | ~150 |
| `bfcl_en` | Gorilla BFCL v4 live originals (Apache-2.0), same ids as BFCL-Hi | ~150 |
| `bfcl_hinglish` | Romanized/code-mixed rewrites of the same tasks (140: 89 native-reviewed, 51 AI-reviewed only) | ~150 |
| `value_heavy` | Written for this project: e-commerce, banking, delivery, booking × 3 langs | 50 × 3 |

Every line is one `harness.schema.Task`. Tasks sharing a `pair_id` are versions of one task.

## Splits (frozen at G0)

- `dev/` (40%) — tune lexicons, prompts, router thresholds here only.
- `test/` (60%) — run once per release. Never read while developing. **Private** until the
  paper: kept in the private repo, published here only as hashes (`SPLITS.lock`,
  `test_ngrams.txt`).
- `SPLITS.lock` records hashes; CI fails if a split file changes without a deliberate re-lock.

## Rebuilding (maintainers)

```sh
scripts/private_sync.sh pull        # sources + test split from the private repo
hf download nvidia/BFCL-Hi --type dataset --revision 500e3062d11fb68a5aa5a878404d62ffaf15f869 \
    --local-dir data/external/bfcl_hi
git clone --depth 1 --filter=blob:none --sparse https://github.com/ShishirPatil/gorilla.git data/external/gorilla
git -C data/external/gorilla fetch -q --depth 1 origin 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8
git -C data/external/gorilla checkout -q 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8
git -C data/external/gorilla sparse-checkout set berkeley-function-call-leaderboard/bfcl_eval/data
uv run python -m harness.importers.bfcl data/external/bfcl_hi \
    data/external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data data/raw \
    --hinglish harness/sources/bfcl_hinglish.yaml
uv run python -m harness.importers.value_heavy harness/sources/value_heavy.yaml data/raw
uv run python -m harness.split assign data/raw harness/tasks
uv run python -m harness.split check harness/tasks    # must still match the frozen lock
```

Changing tasks after G0 means a deliberate re-lock (`split lock`), new hashes
(`python -m harness.leakage --write-hashes`), `scripts/private_sync.sh push`, and a note in
the PR explaining why.
