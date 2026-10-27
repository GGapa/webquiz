# -*- coding: utf-8 -*-
"""Discover which sections contain a quiz and record their status."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .browser import click_section, find_work_frame, hide_overlays, new_context


def catalog_items(page) -> list[dict]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('div.posCatalog_select'))
            .map(e => ({id: e.id, text: (e.innerText||'').trim().replace(/\\s+/g,' ')}))
            .filter(x => x.id.startsWith('cur'))"""
    )


def _score(text: str) -> str:
    m = re.search(r"(?:This time|Final score)\s*([\d.]+)\s*score", text)
    return m.group(1) if m else ""


def discover(cfg, only: list[str] | None = None, save_html: bool = True):
    from playwright.sync_api import sync_playwright

    out_dir = cfg.output_dir
    html_dir = out_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as pw:
        browser, ctx = new_context(pw, cfg)
        page = ctx.new_page()
        page.goto(cfg.main_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        items = catalog_items(page)
        if only:
            items = [x for x in items if any(x["id"].endswith(c) for c in only)]
        print(f"sections: {len(items)}")

        for i, item in enumerate(items, 1):
            cid = item["id"].replace("cur", "")
            click_section(page, cid)
            frame = find_work_frame(page, cid, tries=12, interval_ms=400)
            entry = {
                "index": i,
                "chapterId": cid,
                "catalog": item["text"],
                "hasQuiz": bool(frame),
            }
            if frame:
                try:
                    text = frame.evaluate("() => document.body.innerText")
                    html = frame.content()
                except Exception:
                    text, html = "", ""
                entry.update(
                    {
                        "status": "completed" if "Completed" in text else (
                            "todo" if "To do" in text else "?"
                        ),
                        "score": _score(text),
                        "questions": (
                            re.search(r"Number of questions:\s*(\d+)", text).group(1)
                            if re.search(r"Number of questions:\s*(\d+)", text)
                            else ""
                        ),
                        "url": frame.url,
                    }
                )
                if save_html and html:
                    path = html_dir / f"{i:02d}_{cid}.html"
                    path.write_text(html, encoding="utf-8")
                    entry["html"] = str(path)
            results.append(entry)
            print(
                f"[{i}/{len(items)}] {item['text'][:40]:40} "
                f"{'quiz' if entry['hasQuiz'] else '-':4} "
                f"{entry.get('status',''):9} {entry.get('score','')}"
            )
            hide_overlays(page)

        (out_dir / "discover.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        browser.close()
    return results
