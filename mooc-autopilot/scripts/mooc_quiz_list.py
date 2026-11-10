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

out = {}
with sync_playwright() as pw:
    b = connect(pw)
    ctx = b.contexts[0]
    tab = ctx.new_page()
    for tag, url in COURSES.items():
        tab.goto(url, wait_until="domcontentloaded", timeout=60000); time.sleep(6)
        n = tab.locator("a.j-quizBtn").count()
        ids = []
        for i in range(n):
            try:
                tab.locator("a.j-quizBtn").nth(i).click(timeout=8000)
                time.sleep(4)
                u = tab.url
                if "/quiz?id=" in u:
                    qid = u.split("/quiz?id=")[1].split("&")[0]
                    ids.append(qid)
                tab.go_back()
                time.sleep(4)
                if not tab.url.endswith("testlist"):
                    tab.goto(url, wait_until="domcontentloaded", timeout=60000); time.sleep(5)
            except Exception as e:
                print(f"  {tag} #{i} err {str(e)[:50]}")
                tab.goto(url, wait_until="domcontentloaded", timeout=60000); time.sleep(5)
        out[tag] = {"testlist": url, "ids": ids}
        print(f"{tag}: {len(ids)} quizzes -> {ids}")
    tab.close()
json.dump(out, open("out/mooc_quiz_ids.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved")
