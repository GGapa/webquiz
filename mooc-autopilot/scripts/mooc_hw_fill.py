# -*- coding: utf-8 -*-
"""MOOC 作业填写：按题号往 Quill 编辑器里填答案，可指定某题上传附件。

用法（由外部脚本或人工指定）：
    python scripts/mooc_hw_fill.py --url "<hw url>" --answer-file out/hw_answers.json
答案文件格式：
    {"1": {"text": "...", "file": "C:/path/a.png"}, "2": {"text": "..."}}
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import json
import sys
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from env import connect  # noqa: E402

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__ or "（该脚本没有写文档字符串）")
    raise SystemExit(0)


ROOT = Path(__file__).resolve().parents[1]


import pjs  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

LOG = ROOT / "out" / "mooc_hw.log"


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")


def fill_question(tab, idx: int, text: str) -> bool:
    """往第 idx 个题目的 Quill 编辑器里输入文字（必须真实点击拿焦点）。"""
    ok = tab.evaluate("""(i) => {
        const qs = Array.from(document.querySelectorAll('.u-questionItem'));
        const q = qs[i];
        if (!q) return 0;
        const ed = q.querySelector('.j-answer .ql-editor');
        if (!ed) return 0;
        ed.scrollIntoView({block: 'center'});
        return 1; }""", idx)
    if not ok:
        return False
    try:
        tab.locator(".u-questionItem").nth(idx).locator(".j-answer .ql-editor").first.click(timeout=8000)
    except Exception as exc:  # noqa: BLE001
        log(f"  Q{idx+1} 编辑器点不到 {str(exc)[:60]}")
        return False
    time.sleep(0.4)
    # 先清空编辑器（草稿会被 SPA 恢复，直接输入会叠加）
    tab.keyboard.press("Control+A")
    tab.keyboard.press("Delete")
    time.sleep(0.2)
    tab.keyboard.type(text, delay=4)
    time.sleep(0.6)
    got = tab.evaluate("""(i) => { const q = document.querySelectorAll('.u-questionItem')[i];
        const ed = q ? q.querySelector('.j-answer .ql-editor') : null;
        return ed ? ed.innerText.length : -1; }""", idx)
    log(f"  Q{idx+1} 输入长度 {got}")
    return (got or 0) > 10


def upload(tab, idx: int, path: str) -> bool:
    try:
        inp = tab.locator(".u-questionItem").nth(idx).locator("input[type=file]").first
        inp.set_input_files(path, timeout=30000)
        time.sleep(5)
        log(f"  Q{idx+1} 上传 {Path(path).name}")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"  Q{idx+1} 上传失败 {str(exc)[:80]}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--answer-file", required=True)
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--tag", default="hw")
    a = ap.parse_args()

    answers = json.loads(Path(a.answer_file).read_text(encoding="utf-8-sig"))
    log(f"== {a.tag} {a.url}")
    with sync_playwright() as pw:
        b = connect(pw)
        ctx = b.contexts[0]
        tab = next((p for p in ctx.pages if "icourse163" in p.url), None) or ctx.new_page()
        tab.goto(a.url, wait_until="domcontentloaded", timeout=90000)
        time.sleep(10)
        n = tab.evaluate("() => document.querySelectorAll('.u-questionItem').length")
        log(f"  题目数={n}")
        for i in range(n):
            spec = answers.get(str(i + 1)) or {}
            if spec.get("file"):
                upload(tab, i, spec["file"])
            if spec.get("text"):
                if not fill_question(tab, i, spec["text"]):
                    log(f"  !! Q{i+1} 没填进去")
            time.sleep(1)
        if not a.submit:
            log("  dry：未提交")
            return 0
        # 勾选“学术诚信”复选框，否则提交按钮无效
        tab.evaluate("""() => {
            const cb = document.querySelector('input.j-cxcheck');
            if (cb && !cb.checked) cb.click();
            return 1; }""")
        time.sleep(1)
        tab.evaluate("""() => { const b = document.querySelector('a.j-submit') ||
            Array.from(document.querySelectorAll('a,button')).filter(e => /提交答案/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight)).pop();
            if (b) b.click(); return 1; }""")
        time.sleep(4)
        for _ in range(4):
            tab.evaluate("""() => { const b = Array.from(document.querySelectorAll('a,button,div,span')).filter(e =>
                /^(确定|确认|提交)$/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight));
                if (b.length) b[b.length-1].click(); return 1; }""")
            time.sleep(3)
        t = tab.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ')") or ""
        log(f"  提交后页面片段: {t[:200]}")
        print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
