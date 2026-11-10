# -*- coding: utf-8 -*-
"""生成课程条目清单 out/mooc_plan.json（每个文档/视频/讨论/测验一条，带 learned 状态）。

这是慕课所有批量操作的前置步骤：后面的 video_walk / text_walk 都读这份清单。

用法::

    python scripts/mooc_refresh_plan.py

需要 config.yaml 的 icourse163.courses（课程名 -> 课程内容页 URL）。
"""
from __future__ import annotations

import sys, time, json

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from env import connect  # noqa: E402

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__ or "（该脚本没有写文档字符串）")
    raise SystemExit(0)

from courses import COURSES  # noqa: E402
from playwright.sync_api import sync_playwright

EXPAND = """() => { document.querySelectorAll('.m-learnChapterNormal').forEach(ch => {
    const box = ch.querySelector('.j-lessoBox');
    if (!box || box.children.length === 0) { const t = ch.querySelector('.j-titleBox'); if (t) t.click(); } }); }"""
plan = {}
with sync_playwright() as pw:
    b = connect(pw)
    ctx = b.contexts[0]
    tab = ctx.new_page()
    for name, url in COURSES.items():
        tab.goto(url, wait_until="domcontentloaded", timeout=60000); time.sleep(5)
        for _ in range(6):
            tab.evaluate(EXPAND); time.sleep(2.5)
            if tab.evaluate("() => document.querySelectorAll('.sourceList > div[data-cid]').length") > 10: break
        data = tab.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.m-learnChapterNormal').forEach(ch => {
                const chName = (ch.querySelector('.j-titleName')||{}).innerText || '';
                ch.querySelectorAll('.u-learnLesson').forEach(L => {
                    const items = [];
                    L.querySelectorAll('.sourceList > div[data-cid]').forEach(d => {
                        const t = d.querySelector('.tag');
                        items.push({cid: d.getAttribute('data-cid'),
                                    type: (t?t.innerText:'').trim(),
                                    title: (d.getAttribute('title')||'').slice(0,60),
                                    learned: /\\blearned\\b/.test(d.className||'')});
                    });
                    out.push({chapter: chName.trim().slice(0,30),
                              lesson: ((L.querySelector('.j-name')||{}).innerText||'').trim().slice(0,40),
                              items});
                });
            });
            return out;
        }""")
        plan[name] = {"url": url, "detail": data}
        n_left = sum(1 for L in data for it in L["items"] if not it["learned"])
        print(f"{name}: {n_left} items left")
    tab.close()
json.dump(plan, open("out/mooc_plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("plan refreshed")
