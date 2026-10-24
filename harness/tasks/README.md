# Task sets

| Set | Source | Planned size |
|---|---|---|
| `bfcl_hi` | NVIDIA BFCL-Hi (CC-BY-4.0), read as raw JSON, not via `datasets` | ~150 |
| `bfcl_en` | Gorilla BFCL originals paired with BFCL-Hi (confirm licence) | ~150 |
| `bfcl_hinglish` | Romanized/code-mixed rewrites of the same tasks, hand-checked | ~150 |
| `value_heavy` | Written for this project: e-commerce, banking, delivery, booking × 3 langs | ~150 × 3 |

Every line is one `harness.schema.Task`. Tasks sharing a `pair_id` are versions of one task.

## Splits (frozen at G0)

- `dev/` (40%) — tune lexicons, prompts, router thresholds here only.
- `test/` (60%) — run once per release. Never read while developing.
- `SPLITS.lock` records hashes; CI fails if a split file changes without a deliberate re-lock.

Workflow: write raw tasks outside this folder (e.g. `data/raw/`), then
`python -m harness.split assign data/raw harness/tasks && python -m harness.split lock harness/tasks`.
