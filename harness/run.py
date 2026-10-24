"""Run a task set over a grid of conditions and seeds. Model calls are wired in Week 1.

Conditions are model x quant x language x gateway on/off x seed. Output goes to
harness/reports/<version>/: results.csv (one row per trial) and traces/ (JSONL).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.schema import Task, TrialResult

SEEDS = (0, 1, 2, 3)
TEMPERATURE = 0.7


@dataclass(frozen=True)
class Condition:
    model: str
    quant: str
    gateway: str  # "off", "on", or an ablation: "grammar", "canon", "router"
    base_url: str
    system_prompt: str | None = None  # set for the strong-prompt baseline

    @property
    def name(self) -> str:
        suffix = "+prompt" if self.system_prompt else ""
        return f"{self.model}:{self.quant}:{self.gateway}{suffix}"


def run_trial(task: Task, condition: Condition, seed: int, temperature: float) -> TrialResult:
    """Send one task to ``condition.base_url`` and score the response."""
    raise NotImplementedError("Week 1: call the backend, parse tool calls, score with score.py")


def run_grid(
    tasks: list[Task],
    conditions: list[Condition],
    out_dir: Path,
    seeds: tuple[int, ...] = SEEDS,
    temperature: float = TEMPERATURE,
) -> list[TrialResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return [
        run_trial(task, cond, seed, temperature)
        for cond in conditions
        for task in tasks
        for seed in seeds
    ]
