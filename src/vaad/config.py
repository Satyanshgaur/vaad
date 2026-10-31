"""Gateway configuration, loaded from one YAML file."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl


class Backend(BaseModel):
    url: HttpUrl
    model: str
    api_key: str | None = None
    timeout_s: float = 120.0


class Routing(BaseModel):
    """Rule-based routing thresholds. Tune on the dev split only."""

    min_tools_for_strong: int = 4
    strong_on_indic_with_values: bool = True


class Thresholds(BaseModel):
    """Canonicalizer confidence cut-offs: >= pass passes, >= retry retries, else flag."""

    pass_: float = Field(0.9, validation_alias="pass")
    retry: float = 0.6


class GrammarSettings(BaseModel):
    """Schema tightening and repair. The switches double as the Phase 1 ablations."""

    enabled: bool = True
    date_grammar: Literal["strict", "loose"] = "strict"
    infer_enums: bool = True
    max_length: int = 512
    retry: bool = True


class CanonSettings(BaseModel):
    """Spoken-value handling. ``annotate`` writes parsed values into the user's turn, ``verify``
    checks the model's arguments against the turn (repair, retry or flag), ``both`` does both."""

    mode: Literal["off", "annotate", "verify", "both"] = "off"
    ref_date: date | None = None  # today when None; fixed in evaluations
    ungrounded: Literal["ignore", "flag"] = "ignore"  # a typed value with no support in the turn


class Settings(BaseModel):
    gateway_enabled: bool = True
    small: Backend
    strong: Backend | None = None
    routing: Routing = Routing()
    thresholds: Thresholds = Thresholds()
    grammar: GrammarSettings = GrammarSettings()
    canon: CanonSettings = CanonSettings()
    trace_path: Path | None = Path("traces/vaad.jsonl")
    # Per-tool overrides: {tool_name: {arg_name: value_type | "free_text"}}
    overrides: dict[str, dict[str, str]] = {}


def load_settings(path: str | Path) -> Settings:
    with Path(path).open(encoding="utf-8") as f:
        return Settings.model_validate(yaml.safe_load(f))
