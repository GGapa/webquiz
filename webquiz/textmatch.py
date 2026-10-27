# -*- coding: utf-8 -*-
"""Text normalisation and option matching.

Chaoxing shuffles option order and stores a canonical letter in a ``data``
attribute, while the visible letter is just the position.  We therefore always
match by the option *text*.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

# Compatibility ideographs / Kangxi radicals that show up in the obfuscated text.
RADICAL_MAP = {
    "⺠": "民",
    "⻛": "风",
    "⻔": "门",
    "⻓": "长",
    "⻣": "骨",
    "⻤": "鬼",
    "⻅": "见",
    "⻋": "车",
    "⻢": "马",
    "⻉": "贝",
}

# Characters the font glyph matcher may fail to recover.
UNKNOWN_CHARS = {"▀", "�", "?"}


def normalize(text: str) -> str:
    """Normalize an option text for comparison.

    Important: only strip a leading A-H when it is followed by whitespace.
    Options such as ``B+`` or ``A+`` must keep their letter, otherwise every
    option collapses to ``+`` and matches the first row.
    """
    s = unicodedata.normalize("NFKC", text or "")
    s = re.sub(r"^\s*[A-Ha-h]\s+", "", s)
    for src, dst in RADICAL_MAP.items():
        s = s.replace(src, dst)
    for ch in UNKNOWN_CHARS:
        s = s.replace(ch, "")
    s = re.sub(r"[\s\u3000]+", "", s)
    return s.strip("。.，,；;：:")


def score(wanted: str, candidate: str) -> float:
    """Similarity score. Exact match must beat substring matches.

    ``软件工程`` is a substring of ``软件工程专业导论``; without exact-first the
    wrong row can be clicked, and in multi-select questions that can toggle an
    already selected option off.
    """
    w, c = normalize(wanted), normalize(candidate)
    if not w or not c:
        return 0.0
    if w == c:
        return 1.2
    if w in c or c in w:
        return 1.0
    return difflib.SequenceMatcher(None, w, c).ratio()


def best_match(wanted: str, candidates: list[str], threshold: float = 0.80):
    """Return ``(index, score)`` of the best candidate, or ``(None, 0.0)``."""
    best_i, best_s = None, 0.0
    for i, cand in enumerate(candidates):
        s = score(wanted, cand)
        if s > best_s:
            best_i, best_s = i, s
    if best_i is None or best_s < threshold:
        return None, best_s
    return best_i, best_s
