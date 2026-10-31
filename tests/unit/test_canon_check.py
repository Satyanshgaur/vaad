from __future__ import annotations

from datetime import date

import pytest

from vaad.canon import annotate_turn, check_argument, field_kind

REF = date(2026, 10, 24)
WEIGHT = {"type": "number", "description": "Parcel weight in kilograms"}
AMOUNT = {"type": "number", "description": "Amount in rupees"}
DELIVERY = {"type": "string", "description": "Delivery date, YYYY-MM-DD"}
STATEMENT_END = {"type": "string", "description": "End of the bank statement period, YYYY-MM-DD"}
PHONE = {"type": "string", "description": "10-digit Indian mobile number"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "schema", "kind"),
    [
        ("weight_kg", WEIGHT, "quantity"),
        ("amount_inr", AMOUNT, "money"),
        ("delivery_date", DELIVERY, "date"),
        ("recipient_phone", PHONE, "phone"),
        ("time", {"type": "string", "description": "24-hour HH:MM"}, "time"),
        ("note", {"type": "string", "description": "Free text"}, "other"),
        ("city", {"type": "string"}, "other"),
        ("tenure_months", {"type": "integer"}, "other"),
    ],
)
def test_field_kind(name: str, schema: dict[str, object], kind: str) -> None:
    assert field_kind(name, schema) == kind


@pytest.mark.unit
def test_agree_repair_and_ungrounded() -> None:
    assert check_argument("weight_kg", WEIGHT, 1.5, "dedh kilo cheeni", REF).status == "agree"  # type: ignore[union-attr]
    repair = check_argument("weight_kg", WEIGHT, 15, "dedh kilo cheeni", REF)
    assert repair is not None and repair.status == "repair" and repair.value == 1.5
    assert repair.confidence >= 0.9
    none = check_argument("weight_kg", WEIGHT, 3, "order bhej do", REF)
    assert none is not None and none.status == "ungrounded"
    assert check_argument("note", {"type": "string"}, "x", "dedh kilo", REF) is None


@pytest.mark.unit
def test_money_and_phone_repairs() -> None:
    amount = check_argument("amount_inr", AMOUNT, 1.5, "dedh lakh rupaye bhejo", REF)
    assert amount is not None and amount.value == 150000 and amount.status == "repair"
    phone = check_argument("recipient_phone", PHONE, "981234567", "98123 45670 pe bhejo", REF)
    assert phone is not None and phone.value == "9812345670" and phone.status == "repair"


@pytest.mark.unit
def test_kal_direction_comes_from_the_tense_or_the_field() -> None:
    ok = check_argument("delivery_date", DELIVERY, "2026-10-25", "kal tak bhej do", REF)
    assert ok is not None and ok.status == "agree"
    fix = check_argument("delivery_date", DELIVERY, "2026-10-23", "kal tak bhej do", REF)
    assert fix is not None and fix.status == "repair" and fix.value == "2026-10-25"
    past = check_argument("to_date", STATEMENT_END, "2026-10-23", "1 October se kal tak", REF)
    assert past is not None and past.status == "agree"  # the field says statement: past


@pytest.mark.unit
def test_agreeing_with_an_ambiguous_reading_is_still_ambiguous() -> None:
    bare = {"type": "string", "description": "Date, YYYY-MM-DD"}
    got = check_argument("date", bare, "2026-10-25", "kal", REF)
    assert got is not None and got.status == "ambiguous" and got.confidence < 0.6
    time = check_argument(
        "time", {"type": "string", "description": "24-hour HH:MM"}, "17:00", "paanch baje", REF
    )
    assert time is not None and time.status == "ambiguous"


@pytest.mark.unit
def test_annotate_turn_marks_only_spoken_forms() -> None:
    out = annotate_turn(
        "dedh kilo cheeni, kal tak bhej do, saade nau baje subah, 2 kilo, 500 rupaye", REF
    )
    assert "dedh [=1.5] kilo" in out and "[=09:30]" in out and "[=2026-10-25]" in out
    assert "2 kilo," in out and "[=2]" not in out and "[=500]" not in out
    assert annotate_turn("hello", REF) == "hello"
    assert "[=" not in annotate_turn("kal tak", REF)  # no tense cue: not sure enough to annotate


@pytest.mark.unit
def test_phone_numbers_are_masked_in_the_audit_helper() -> None:
    from vaad.server.pipeline import _mask

    assert _mask("9812345670") == "XXXXXXXX70"


@pytest.mark.unit
def test_canon_version_changes_with_the_lexicons() -> None:
    from vaad.canon.version import canon_version

    assert canon_version().startswith("0.") and "+lex." in canon_version()
