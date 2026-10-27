# -*- coding: utf-8 -*-
"""Fill answers into a quiz/homework page and submit."""
from __future__ import annotations

import re
import unicodedata

from .browser import hide_overlays
from .fontdecode import decode_text
from .textmatch import best_match


def _live_text(raw: str, mapping) -> str:
    text = decode_text(raw, mapping)
    return unicodedata.normalize("NFKC", text)


def fill_quiz(frame, questions: list[dict], answers: dict, mapping, dry: bool = False):
    """Click options by text. ``answers`` is {"1": ["C"], ...}."""
    log = []
    wrappers = frame.locator("div.singleQuesId")
    n = wrappers.count()
    for i in range(n):
        q = wrappers.nth(i)
        qid = q.get_attribute("data") or (q.get_attribute("id") or "").replace("question", "")
        qd = questions[i] if i < len(questions) else None
        letters = answers.get(str(i + 1), [])
        wanted = [qd["options"].get(L) for L in letters] if qd else []
        lis = q.locator("li")
        count = lis.count()
        candidates = [_live_text(lis.nth(j).inner_text(), mapping) for j in range(count)]
        clicked = []
        for want in wanted:
            if not want:
                log.append((i + 1, qid, "missing option letter", None))
                continue
            idx, sc = best_match(want, candidates)
            if idx is None:
                log.append((i + 1, qid, f"no match: {want}", sc))
                continue
            if not dry:
                lis.nth(idx).click()
            clicked.append((want, sc))
        try:
            value = frame.eval_on_selector(f"#answer{qid}", "e => e.value")
        except Exception:
            value = "?"
        log.append((i + 1, qid, clicked, value))
    return log


def submit_frame(frame, page, wait_ms: int = 4000) -> str:
    """Submit a doHomeWorkNew frame; returns the page text after submit."""
    frame.evaluate("() => { try { toadd(['','']) } catch(e) { console.log(e) } }")
    page.wait_for_timeout(300)
    frame.evaluate("() => form1submit()")
    page.wait_for_timeout(wait_ms)
    try:
        return frame.evaluate("() => document.body.innerText")
    except Exception:
        return ""


def retake_frame(frame, page) -> bool:
    """Click the visible Redo link and confirm. Returns True if a new attempt opened."""
    try:
        link = frame.locator("a", has_text="Redo").first
        if link.count() == 0:
            return False
        link.click()
        page.wait_for_timeout(800)
        if frame.is_visible("#workpop"):
            frame.click("#workpop #popok")
        page.wait_for_timeout(2500)
        return True
    except Exception:
        return False


def score_from_text(text: str) -> str:
    m = re.search(r"(?:This time|Final score)\s*([\d.]+)\s*score", text or "")
    return m.group(1) if m else ""


def fill_homework(page, questions: list[dict], answers: dict, mapping, dry: bool = False):
    """Fill a mooc2/work/dowork page (returns a log)."""
    log = []
    wrappers = page.locator("div.singleQuesId")
    for i in range(wrappers.count()):
        q = wrappers.nth(i)
        qid = q.get_attribute("data") or (q.get_attribute("id") or "").replace("question", "")
        qd = questions[i] if i < len(questions) else None
        wanted = [qd["options"].get(L) for L in answers.get(str(i + 1), [])] if qd else []
        opts = q.locator("div.answerBg")
        candidates = [_live_text(opts.nth(j).inner_text(), mapping) for j in range(opts.count())]
        clicked = []
        for want in wanted:
            if not want:
                continue
            idx, sc = best_match(want, candidates)
            if idx is None:
                log.append((i + 1, qid, f"no match: {want}", sc))
                continue
            if not dry:
                opts.nth(idx).click()
            clicked.append((want, sc))
        try:
            value = page.eval_on_selector(f"#answer{qid}", "e => e.value")
        except Exception:
            value = "?"
        log.append((i + 1, qid, clicked, value))
    return log


def submit_homework(page, wait_ms: int = 5000) -> str:
    page.click("a.completeBtn")
    shown = False
    for _ in range(20):
        page.wait_for_timeout(500)
        if page.is_visible("#workpop"):
            shown = True
            break
    if shown:
        page.click("#popok")
    page.wait_for_timeout(wait_ms)
    return page.evaluate("() => document.body.innerText")
