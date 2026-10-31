"""Indian mobile numbers, typed or spoken digit by digit, as a 10-digit string.

A phone number here is a run of digits (typed, or spoken as words, with "double"/"triple" for
repeats) that is exactly 10 digits after dropping +91 / 91 / 0. A number that is too short or too
long, or does not start with 6-9, is not returned as a confident phone number.
"""

from __future__ import annotations

from vaad.canon.tokens import DEVANAGARI_DIGITS, Token, tokenize
from vaad.types import Canonicalized, Span

_DIGIT_WORDS = {
    **{
        w: d
        for d, ws in enumerate(
            [
                "zero shunya oh o जीरो ज़ीरो शून्य",
                "ek one एक",
                "do two दो",
                "teen three तीन",
                "char chaar four चार फोर",
                "paanch panch five पांच पाँच",
                "chhe chhey chhah che six छह छः छे छ सिक्स",
                "saat seven सात",
                "aath eight आठ",
                "nau nine नौ",
            ]
        )
        for w in ws.split()
    },
}
_REPEAT = {"double": 2, "triple": 3, "डबल": 2, "दुगुना": 2, "ट्रिपल": 3, "tripple": 3, "dabal": 2}
_MIN_RUN = 7  # shorter runs cannot be a phone number; avoids reading "ek do teen" as digits


def _digit_of(token: Token) -> str | None:
    if token.kind == "digits":
        return token.text.translate(DEVANAGARI_DIGITS).replace(",", "").replace(".", "")
    value = _DIGIT_WORDS.get(token.norm)
    return None if value is None else str(value)


def _runs(text: str) -> list[tuple[str, int, int, bool]]:
    """(digits, start, end, spoken) for each maximal run of digit tokens."""
    tokens = tokenize(text)
    runs: list[tuple[str, int, int, bool]] = []
    digits, start, end, spoken, i = "", 0, 0, False, 0
    while i < len(tokens):
        token = tokens[i]
        repeat = _REPEAT.get(token.norm)
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        piece: str | None
        if repeat and nxt is not None and (d := _digit_of(nxt)) is not None and len(d) == 1:
            piece, consumed, was_spoken = d * repeat, 2, True
        else:
            piece, consumed, was_spoken = _digit_of(token), 1, token.kind == "word"
        if token.text == "+" and nxt is not None and nxt.kind == "digits":
            i += 1  # "+91" prefix: keep the digits that follow
            continue
        if piece is not None:
            if not digits:
                start = token.start
            digits += piece
            end = tokens[i + consumed - 1].end
            spoken = spoken or was_spoken
            i += consumed
            continue
        if (
            token.kind == "sym"
            and token.text in "-,"
            and digits
            and nxt is not None
            and _digit_of(nxt)
        ):
            i += 1  # separators inside a number
            continue
        if digits:
            runs.append((digits, start, end, spoken))
            digits = ""
        i += 1
    if digits:
        runs.append((digits, start, end, spoken))
    return runs


def parse_phone(text: str) -> Canonicalized | None:
    """The first 10-digit Indian mobile number in ``text``; None if there is none."""
    for digits, start, end, spoken in _runs(text):
        if len(digits) < _MIN_RUN:
            continue
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if len(digits) != 10:
            continue
        valid_start = digits[0] in "6789"
        conf = (0.9 if spoken else 0.95) if valid_start else 0.5
        why = ("spoken digits" if spoken else "typed digits") + (
            "" if valid_start else "; starts below 6"
        )
        return Canonicalized(digits, conf, Span(start, end), why)
    return None


__all__ = ["parse_phone"]
