import json

import pytest

from vaad.cli import main


def test_parse_prints_values_and_asks_when_the_time_has_no_part_of_day(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(["parse", "kal saade aath baje dedh hazaar rupaye", "--ref-date", "2026-11-05"]) == 0
    )
    out = json.loads(capsys.readouterr().out)
    by_kind = {v["kind"]: v for v in out["values"]}
    assert by_kind["amount"]["value"] == 1500
    assert by_kind["date"]["value"] == "2026-11-06"
    assert by_kind["time"]["confidence"] < 0.6
    assert "[=1500]" in out["annotated"]
