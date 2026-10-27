# -*- coding: utf-8 -*-
"""Playwright helpers and cookie loading."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from playwright.sync_api import BrowserContext, Frame, Page


def load_cookies(path: Path) -> list[dict]:
    """Load a raw ``Cookie:`` header or a JSON cookie array."""
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        raise ValueError(f"cookie file is empty: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        return [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain") or ".chaoxing.com",
                "path": c.get("path") or "/",
            }
            for c in data
        ]
    raw = re.sub(r"^\s*cookie\s*:\s*", "", raw, flags=re.I)
    cookies = []
    for part in raw.split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        cookies.append(
            {"name": name, "value": value, "domain": ".chaoxing.com", "path": "/"}
        )
    if not cookies:
        raise ValueError(f"could not parse cookies: {path}")
    return cookies


def new_context(pw, cfg):
    launch = {
        "channel": cfg.browser.get("channel", "chrome"),
        "headless": bool(cfg.browser.get("headless", False)),
    }
    slow = int(cfg.browser.get("slow_mo_ms", 0))
    if slow:
        launch["slow_mo"] = slow
    browser = pw.chromium.launch(
        **launch, args=["--disable-blink-features=AutomationControlled"]
    )
    ctx: BrowserContext = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_cookies(load_cookies(cfg.cookie_file))
    return browser, ctx


def find_work_frame(page: Page, chapter_id: str | None = None, tries: int = 40,
                    interval_ms: int = 300) -> Frame | None:
    for _ in range(tries):
        for f in page.frames:
            if f.name != "frame_content" or "/work/" not in f.url:
                continue
            if chapter_id and chapter_id not in f.url:
                continue
            return f
        page.wait_for_timeout(interval_ms)
    return None


def hide_overlays(page: Page) -> None:
    try:
        page.evaluate(
            """() => { try {
                $('#workpop').hide(); $('#worktoast').hide();
                $('.maskDiv,.maskTipDiv').hide();
            } catch(e) {} }"""
        )
    except Exception:
        pass


def click_section(page: Page, chapter_id: str, timeout: int = 10000) -> None:
    hide_overlays(page)
    page.click(f"div#cur{chapter_id}", timeout=timeout)
