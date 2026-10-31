"""Shared tokenizer for the canon parsers: words (Roman or Devanagari), digit runs, symbols."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(
    r"(?P<digits>[0-9०-९][0-9०-९,]*(?:\.[0-9०-९]+)?)"  # noqa: RUF001
    r"|(?P<word>[A-Za-zऀ-॥॰-ॿ]+)"
    r"|(?P<sym>\S)"
)
DEVANAGARI_DIGITS = {0x0966 + i: ord(str(i)) for i in range(10)}


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    start: int
    end: int
    kind: str  # "digits", "word" or "sym"

    @property
    def norm(self) -> str:
        return self.text.lower()


def tokenize(text: str) -> list[Token]:
    return [
        Token(m.group(), m.start(), m.end(), m.lastgroup or "sym") for m in _TOKEN.finditer(text)
    ]
