from __future__ import annotations

import pytest

from harness.metrics import (
    bootstrap_ci,
    intervals_overlap,
    paired_bootstrap_ci,
    pass_at_k,
    pass_hat_k,
    per_task_scores,
    percentile,
)


@pytest.mark.unit
class TestPassK:
    def test_all_pass(self) -> None:
        assert pass_hat_k(4, 4, 4) == 1.0
        assert pass_at_k(4, 4, 4) == 1.0

    def test_one_failure_breaks_pass_hat_k_at_full_k(self) -> None:
        assert pass_hat_k(4, 3, 4) == 0.0
        assert pass_at_k(4, 3, 4) == 1.0

    def test_known_values(self) -> None:
        # C(3,2)/C(4,2) = 3/6
        assert pass_hat_k(4, 3, 2) == pytest.approx(0.5)
        # 1 - C(2,2)/C(4,2) = 1 - 1/6
        assert pass_at_k(4, 2, 2) == pytest.approx(5 / 6)
        assert pass_at_k(4, 1, 1) == pytest.approx(0.25)

    def test_pass_hat_k_never_exceeds_pass_at_k(self) -> None:
        for n in range(1, 7):
            for c in range(n + 1):
                for k in range(1, n + 1):
                    assert pass_hat_k(n, c, k) <= pass_at_k(n, c, k) + 1e-12

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k(4, 5, 1)
        with pytest.raises(ValueError):
            pass_at_k(4, 2, 5)

    def test_per_task_scores(self) -> None:
        trials = [[True] * 4, [True, True, True, False], [False] * 4]
        assert per_task_scores(trials, 4) == [1.0, 0.0, 0.0]
        assert per_task_scores(trials, 1, metric="pass@k") == [1.0, 0.75, 0.0]


@pytest.mark.unit
class TestBootstrap:
    def test_deterministic_with_seed(self) -> None:
        values = [0.0, 1.0] * 50
        assert bootstrap_ci(values, 2000, seed=7) == bootstrap_ci(values, 2000, seed=7)

    def test_interval_contains_mean(self) -> None:
        mean, lo, hi = bootstrap_ci([0.0] * 30 + [1.0] * 70, 2000)
        assert mean == pytest.approx(0.7)
        assert lo < mean < hi
        assert lo > 0.55 and hi < 0.85

    def test_constant(self) -> None:
        assert bootstrap_ci([1.0] * 10, 500) == (1.0, 1.0, 1.0)

    def test_overlap(self) -> None:
        assert intervals_overlap((0.5, 0.4, 0.6), (0.55, 0.5, 0.7))
        assert not intervals_overlap((0.3, 0.2, 0.4), (0.6, 0.5, 0.7))


@pytest.mark.unit
def test_percentile() -> None:
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile([3.0], 95) == 3.0


@pytest.mark.unit
class TestPairedBootstrap:
    def test_consistent_gain_is_significant_even_when_intervals_overlap(self) -> None:
        control = [0.0, 0.25, 0.5, 0.75, 1.0] * 8
        treatment = [min(1.0, c + 0.25) for c in control]
        assert intervals_overlap(bootstrap_ci(treatment, 2000), bootstrap_ci(control, 2000))
        mean, lo, _ = paired_bootstrap_ci(treatment, control, 2000)
        assert mean > 0 and lo > 0

    def test_no_difference(self) -> None:
        assert paired_bootstrap_ci([0.5] * 10, [0.5] * 10, 500) == (0.0, 0.0, 0.0)

    def test_length_mismatch(self) -> None:
        with pytest.raises(ValueError):
            paired_bootstrap_ci([1.0], [1.0, 0.0])
