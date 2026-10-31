"""Number words: "nau sau", "नौ सौ", "dedh", "dhai", "2.5k" -> 900, 900, 1.5, 2.5, 2500.

Spoken Hindi numbers are additive-multiplicative: "do hazaar paanch sau" is 2*1000 + 5*100.
Fractions use sava (+1/4), saade (+1/2) and paune (-1/4) before a number; dedh and dhai are 1.5
and 2.5. Every match carries its character span in the input and a confidence, and nothing is
returned for text that is not a number (a bare "bhej do" is a verb, not 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from vaad.canon.lexicon import NumberLexicon, number_lexicon
from vaad.canon.tokens import DEVANAGARI_DIGITS as _DEVANAGARI_DIGITS
from vaad.canon.tokens import Token as _Token
from vaad.canon.tokens import tokenize as _tokenize
from vaad.types import Canonicalized, Span

_CONJUNCTIONS = frozenset({"aur", "ya", "to", "phir", "bas", "na", "please", "plz", "ji", "hai"})
_SUFFIXES = {"k": 1000, "cr": 10_000_000}
# Letters that may touch a digit and still leave it a quantity ("2kg", "5L", "9pm"); any other
# letters touching a digit make it part of an identifier ("OD4821", "U123456").
_UNIT_SUFFIXES = frozenset(
    {
        "k",
        "cr",
        "l",
        "ml",
        "kg",
        "g",
        "gm",
        "km",
        "m",
        "cm",
        "mm",
        "hr",
        "hrs",
        "am",
        "pm",
        "rs",
        "st",
        "nd",
        "rd",
        "th",
    }
)


@dataclass(frozen=True, slots=True)
class NumberMatch:
    value: int | float
    start: int
    end: int
    confidence: float
    reason: str

    def canonicalized(self) -> Canonicalized:
        return Canonicalized(self.value, self.confidence, Span(self.start, self.end), self.reason)


def _digits_value(token: _Token) -> Fraction:
    return Fraction(token.text.translate(_DEVANAGARI_DIGITS).replace(",", ""))


def _as_number(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


class _Phrase:
    """Greedy parse of one number phrase starting at a token index."""

    def __init__(self, tokens: list[_Token], start: int, lex: NumberLexicon) -> None:
        self.tokens, self.lex = tokens, lex
        self.total = Fraction(0)
        self.cur = Fraction(0)
        self.have_cur = False
        self.last = "start"  # start | unit | mult
        self.last_closed = 0  # the largest-first rule: lakh before hazaar before sau
        self.pos = start
        self.end = start
        self.confidence = 1.0
        self.notes: list[str] = []
        self.parsed_any = False
        self.snapshot: tuple[Fraction, bool] = (Fraction(0), False)

    # --- context checks for words that are numbers only sometimes -----------------------
    def _is_number_here(self, index: int) -> tuple[bool, float, str]:
        word = self.tokens[index].norm
        nxt = self.tokens[index + 1] if index + 1 < len(self.tokens) else None
        prev = self.tokens[index - 1] if index > 0 else None
        follower = nxt is not None and (
            nxt.norm in self.lex.number_followers or nxt.norm in self.lex.multipliers
        )
        if word in ("saath", "sath"):
            if follower or self.last == "mult":
                return True, 0.85, f"'{word}' read as sixty (followed by a quantity)"
            return False, 0.0, ""
        if word in ("do", "doh", "दो"):
            if prev is not None and prev.kind == "word" and prev.norm in self.lex.verb_stems:
                return False, 0.0, ""
            if follower:
                return True, 0.95, f"'{word}' read as 2 (followed by a quantity)"
            if nxt is None or nxt.kind == "sym" or nxt.norm in _CONJUNCTIONS:
                return False, 0.0, ""
            return True, 0.65, f"'{word}' read as 2 (no verb before it)"
        if word in ("ek", "एक"):
            bare = not follower
            return True, 0.7 if bare else 0.9, f"'{word}' read as 1"
        return True, 1.0, ""

    def _mark(self) -> int:
        """Start of a coefficient: remember the running value so a bad group can be dropped."""
        self.snapshot = (self.cur, self.have_cur)
        return self.pos

    def _close_group(self, multiplier: int, coefficient: Fraction, began: int) -> bool:
        if self.last_closed and multiplier >= self.last_closed:
            # a bigger group after a smaller one is not part of this number: drop its coefficient
            self.pos = self.end = began
            self.cur, self.have_cur = self.snapshot
            return False
        self.total += coefficient * multiplier
        self.cur, self.have_cur, self.last_closed = Fraction(0), False, multiplier
        return True

    def _accept(self, new_pos: int, last: str) -> None:
        self.pos = self.end = new_pos
        self.last = last
        self.parsed_any = True

    def run(self) -> bool:
        tokens, lex = self.tokens, self.lex
        coefficient_start = self._mark()
        while self.pos < len(tokens):
            t = tokens[self.pos]
            word = t.norm
            if t.kind == "digits":
                if self.last not in ("start", "mult"):
                    break
                coefficient_start = self._mark()
                self.cur += _digits_value(t)
                self.have_cur = True
                nxt = self.pos + 1
                if (
                    nxt < len(tokens)
                    and tokens[nxt].start == t.end
                    and tokens[nxt].norm in _SUFFIXES
                ):
                    if not self._close_group(
                        _SUFFIXES[tokens[nxt].norm], self.cur, coefficient_start
                    ):
                        break
                    self._accept(nxt + 1, "mult")
                    self.notes.append("digits with k/cr suffix")
                    continue
                self.notes.append("digits")
                self._accept(self.pos + 1, "unit")
                continue
            if t.kind != "word":
                break
            if word in lex.modifiers:
                follows = self.pos + 1 < len(tokens)
                nxt_t = tokens[self.pos + 1] if follows else None
                if nxt_t is None or self.last not in ("start", "mult"):
                    break
                coefficient_start = self._mark()
                if nxt_t.norm in lex.multipliers:  # "sava sau": one and a quarter hundreds
                    self.cur = Fraction(1) + lex.modifiers[word]
                    self.have_cur = True
                    self.notes.append(f"{word} before a multiplier")
                    self._accept(self.pos + 1, "unit")
                    continue
                if nxt_t.kind == "digits":
                    base = _digits_value(nxt_t)
                elif (
                    nxt_t.norm in lex.units and nxt_t.norm not in lex.ambiguous
                ) or nxt_t.norm in lex.units:
                    base = Fraction(lex.units[nxt_t.norm])
                else:
                    break
                self.cur = base + lex.modifiers[word]
                self.have_cur = True
                self.notes.append(f"{word} {nxt_t.text}")
                self._accept(self.pos + 2, "unit")
                continue
            if word in lex.fractions:
                if self.last not in ("start", "mult"):
                    break
                coefficient_start = self._mark()
                self.cur += lex.fractions[word]
                self.have_cur = True
                self.notes.append(f"fraction word {word}")
                self._accept(self.pos + 1, "unit")
                continue
            if word in lex.units:
                if self.last not in ("start", "mult"):
                    break
                ok, conf, note = self._is_number_here(self.pos)
                if word in lex.ambiguous and not ok:
                    break
                if word not in lex.ambiguous:
                    ok, conf, note = True, 1.0, ""
                coefficient_start = self._mark()
                self.cur += lex.units[word]
                self.have_cur = True
                self.confidence = min(self.confidence, conf)
                if note:
                    self.notes.append(note)
                self._accept(self.pos + 1, "unit")
                continue
            if word in lex.multipliers:
                m = lex.multipliers[word]
                if self.last == "unit" or (self.last == "mult" and m < 100) or self.last == "start":
                    pass
                if self.last == "mult" and m >= 1000 and not self.have_cur:
                    break
                if self.last == "start":
                    coefficient_start = self._mark()
                    self.confidence = min(self.confidence, 0.9)
                coefficient = self.cur if self.have_cur else Fraction(1)
                if m == 100:
                    self.cur, self.have_cur = coefficient * 100, True
                    self._accept(self.pos + 1, "mult")
                else:
                    if not self._close_group(m, coefficient, coefficient_start):
                        break
                    self._accept(self.pos + 1, "mult")
                self.notes.append(f"multiplier {word}")
                continue
            break
        return self.parsed_any

    @property
    def value(self) -> Fraction:
        return self.total + self.cur


def _inside_identifier(tokens: list[_Token], i: int) -> bool:
    """A digit run glued to letters that are not a unit suffix is part of an ID, not a quantity."""
    token = tokens[i]
    if token.kind != "digits":
        return False
    before = tokens[i - 1] if i > 0 else None
    after = tokens[i + 1] if i + 1 < len(tokens) else None
    if before is not None and before.kind == "word" and before.end == token.start:
        return True
    return (
        after is not None
        and after.kind == "word"
        and after.start == token.end
        and after.norm not in _UNIT_SUFFIXES
    )


def find_numbers(text: str) -> list[NumberMatch]:
    """Every number expression in ``text``, left to right, with spans."""
    lex = number_lexicon()
    tokens = _tokenize(text)
    matches: list[NumberMatch] = []
    i = 0
    while i < len(tokens):
        if _inside_identifier(tokens, i):
            i += 1
            continue
        phrase = _Phrase(tokens, i, lex)
        if phrase.run() and phrase.end > i:
            first, last = tokens[i], tokens[phrase.end - 1]
            reason = "; ".join(dict.fromkeys(phrase.notes)) or "number words"
            matches.append(
                NumberMatch(
                    _as_number(phrase.value), first.start, last.end, phrase.confidence, reason
                )
            )
            i = phrase.end
        else:
            i += 1
    return matches


def parse_number(text: str) -> Canonicalized | None:
    """Parse the first number expression in ``text``; None if there is none."""
    matches = find_numbers(text)
    return matches[0].canonicalized() if matches else None
