from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vaad.canon.decide import decide
from vaad.config import Thresholds, load_settings
from vaad.grammar import validate
from vaad.server.app import create_app
from vaad.types import Canonicalized, Decision

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_healthz() -> None:
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.unit
def test_example_config_loads() -> None:
    settings = load_settings(ROOT / "config" / "vaad.example.yaml")
    assert settings.small.model
    assert settings.thresholds.pass_ > settings.thresholds.retry


@pytest.mark.unit
def test_validate_reports_errors() -> None:
    schema = {
        "type": "object",
        "properties": {"weight_kg": {"type": "number"}},
        "required": ["weight_kg"],
    }
    assert validate({"weight_kg": 2}, schema) == []
    errors = validate({"weight_kg": "do kilo"}, schema)
    assert len(errors) == 1 and errors[0].startswith("weight_kg:")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("confidences", "expected"),
    [
        ([], Decision.PASS),
        ([0.95, 0.99], Decision.PASS),
        ([0.95, 0.7], Decision.RETRY),
        ([0.95, 0.3], Decision.FLAG),
    ],
)
def test_decide_uses_weakest(confidences: list[float], expected: Decision) -> None:
    results = [Canonicalized(value=1, confidence=c, source=None, reason="") for c in confidences]
    assert decide(results, Thresholds()) is expected


@pytest.mark.unit
def test_unquoted_yaml_off_means_off() -> None:
    import yaml

    from vaad.config import CanonSettings

    assert CanonSettings.model_validate(yaml.safe_load("mode: off")).mode == "off"
    assert CanonSettings.model_validate(yaml.safe_load('mode: "both"')).mode == "both"
