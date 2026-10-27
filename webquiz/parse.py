# -*- coding: utf-8 -*-
"""Parse a Chaoxing quiz page into structured questions."""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

from .fontdecode import decode_text


def parse_questions(html: str, mapping: dict[int, tuple[str, float]] | None = None):
    mapping = mapping or {}
    soup = BeautifulSoup(html, "lxml")
    questions = []

    for box in soup.select("div.TiMu"):
        qid = box.get("data") or (box.get("id") or "").replace("question", "")
        title_el = box.select_one(".Zy_TItle")
        title = decode_text(title_el.get_text(" ", strip=True), mapping) if title_el else ""
        mtype = re.search(r"【([^】]+)】", title)
        qtype = mtype.group(1) if mtype else ""
        stem = re.sub(r"【[^】]+】", "", title)
        stem = re.sub(r"^\s*\d+\s*", "", stem)
        stem = re.sub(r"[（(]\s*\d+(?:\.\d+)?\s*score\s*[)）]", "", stem)
        stem = re.sub(r"\s*\d+(?:\.\d+)?score.*$", "", stem).strip()

        options: dict[str, str] = {}
        for li in box.select("ul.Zy_ulTop li"):
            num = li.select_one("span.num_option, span.num_option_dx")
            letter = ""
            if num:
                letter = (num.get_text(strip=True) or num.get("data") or "").strip()
            if not letter:
                i = li.find("i")
                if i:
                    letter = re.sub(r"[^A-Ha-h]", "", i.get_text(strip=True)).upper()
            if not letter:
                m = re.match(r"\s*([A-Ha-h])[、\.\)\s]", li.get_text(" ", strip=True))
                if m:
                    letter = m.group(1).upper()
            a = li.select_one("a p") or li.select_one("a")
            text = decode_text(a.get_text(" ", strip=True), mapping) if a else ""
            text = re.sub(r"\s*\d+(?:\.\d+)?score.*$", "", text).strip()
            if letter and text and letter not in options:
                options[letter] = text

        if not options and ("True" in qtype or "False" in qtype or "判断" in qtype):
            options = {"A": "True", "B": "False"}

        questions.append(
            {
                "no": len(questions) + 1,
                "qid": qid,
                "type": qtype,
                "stem": stem,
                "options": options,
            }
        )
    return questions
