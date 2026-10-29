"""Deterministic Devanagari to chat-style Roman script (the script control of H6).

Only Devanagari spans change; Latin text, digits, names and punctuation are left alone. The
output is meant to look like typed Hindi ("mera order kal tak bhej do"), not to be a faithful
transliteration scheme: ITRANS first, then a schwa-deletion heuristic (Hindi drops the inherent
"a" at the end of a word and in some medial syllables), then long vowels, retroflex and nasal
marks are folded to plain lower-case letters. Loanword vowels (ऑ, ॉ) become "o".
"""

from __future__ import annotations

import re

from indic_transliteration import sanscript

_DEVANAGARI_RUN = re.compile(r"[ऀ-ॿ]+")
_PRE = (("ॉ", "ो"), ("ऑ", "ओ"), ("ॅ", "े"), ("ऍ", "ए"),
        ("।", "."), ("॥", "."))  # fmt: skip
_FOLDS = (
    (".Dh", "rh"), (".D", "r"), ("RRi", "ri"), ("R^i", "ri"), ("~N", "n"), ("~n", "n"),
    (".N", "n"), (".n", "n"), ("M", "n"), ("H", "h"), ("GY", "gy"), ("kSh", "ksh"),
    (".h", ""), ("OM", "om"),
)  # fmt: skip
_CONSONANT = "bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ"
_FINAL_SCHWA = re.compile(rf"(?<=[{_CONSONANT}])a$")
# medial schwa between a vowel+consonant and a consonant+vowel: pa-ra-soM -> par-soM
_MEDIAL_SCHWA = re.compile(rf"(?<=[aeiouAEIOU][{_CONSONANT}])a(?=[{_CONSONANT}]+[aeiouAEIOU])")


def _word(run: str) -> str:
    for source, target in _PRE:
        run = run.replace(source, target)
    text = sanscript.transliterate(run, sanscript.DEVANAGARI, sanscript.ITRANS)
    for source, target in _FOLDS:
        text = text.replace(source, target)
    if len(text) > 2 and not text.endswith(("iya", "uya")):
        text = _FINAL_SCHWA.sub("", text)
    text = _MEDIAL_SCHWA.sub("", text)
    return text.lower()


def romanize_hindi(text: str) -> str:
    """Romanize every Devanagari span in ``text``."""
    return _DEVANAGARI_RUN.sub(lambda m: _word(m.group()), text)
