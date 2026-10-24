"""Reliability metrics and bootstrap intervals.

For a task run ``n`` times with ``c`` successes:

- pass@k  = 1 - C(n-c, k) / C(n, k): at least one of k sampled trials succeeds.
- pass^k  = C(c, k) / C(n, k): all k sampled trials succeed (tau-bench's reliability metric).

Both are unbiased estimators averaged over tasks. With n == k, pass^k is 1 only if every
trial passed.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from math import ceil, comb
from statistics import fmean


def pass_at_k(n: int, c: int, k: int) -> float:
    _check(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    _check(n, c, k)
    return comb(c, k) / comb(n, k)


def _check(n: int, c: int, k: int) -> None:
    if not (0 <= c <= n and 1 <= k <= n):
        raise ValueError(f"need 0 <= c <= n and 1 <= k <= n, got n={n} c={c} k={k}")


def per_task_scores(
    successes: Sequence[Sequence[bool]], k: int, metric: str = "pass^k"
) -> list[float]:
    """One score per task from its trial outcomes."""
    fn = pass_hat_k if metric == "pass^k" else pass_at_k
    return [fn(len(trials), sum(trials), k) for trials in successes]


def bootstrap_ci(
    values: Sequence[float], n_resamples: int = 10_000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    """Percentile bootstrap over tasks. Returns (mean, low, high)."""
    if not values:
        raise ValueError("no values")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(fmean(rng.choices(values, k=n)) for _ in range(n_resamples))
    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return fmean(values), lo, hi


def intervals_overlap(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    """A gain counts as real only when this is False."""
    return a[1] <= b[2] and b[1] <= a[2]


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile, q in [0, 100]; used for latency p50/p95."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, ceil(q / 100 * len(ordered)) - 1))
    return ordered[rank]
