# -*- coding: utf-8 -*-
"""MOOC 课件里的「随堂测验/随堂测试」：解析 → 模型作答 → 勾选 → 提交 → 核验。

这类条目是嵌在课件页里的（`#/learn/content?type=detail&id=...&cid=...`），
题目结构和大测验一样（`.u-questionItem` / `.j-choicebox ul.choices > li`），
但没有倒计时、也不需要“开始测验”，直接答完点「提交」。

用法： python scripts/mooc_suip.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import sys
import time
import urllib.request

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from env import connect  # noqa: E402

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__ or "（该脚本没有写文档字符串）")
    raise SystemExit(0)

from courses import COURSES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


import pjs  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

LOG = ROOT / "out" / "mooc_suip.log"
STATE = ROOT / "out" / "mooc_suip_state.json"
LIST = "https://www.icourse163.org/learn/HDU-1472757175#/learn/content"
CIDs = ["1322045179", "1322045183", "1322045189", "1322045191"]

PARSE_JS = """() => {
    const qs = Array.from(document.querySelectorAll('.u-questionItem'));
    return qs.map((q, i) => {
        const cat = (q.querySelector('.qaCate') || {}).innerText || '';
        const stem = ((q.querySelector('.j-richTxt') || {}).innerText || '').replace(/\\s+/g, ' ').trim();
        const opts = [];
        q.querySelectorAll('.j-choicebox ul.choices > li').forEach(li => {
            const pos = ((li.querySelector('.optionPos') || {}).innerText || '').trim().replace('.', '');
            const txt = ((li.querySelector('.optionCnt') || {}).innerText || '').replace(/\\s+/g, ' ').trim();
            opts.push({letter: pos, text: txt});
        });
        return {no: i + 1, cat: cat.replace(/\\s+/g, ' ').trim(), stem, opts, multi: /多选/.test(cat)};
    });
}"""

FILL_JS = """(ans) => {
    const qs = Array.from(document.querySelectorAll('.u-questionItem'));
    let checked = 0;
    qs.forEach((q, i) => {
        const want = ans[String(i + 1)] || [];
        q.querySelectorAll('.j-choicebox ul.choices > li').forEach(li => {
            const pos = ((li.querySelector('.optionPos') || {}).innerText || '').trim().replace('.', '');
            const inp = li.querySelector('input');
            if (!inp) return;
            if (want.indexOf(pos) >= 0 && !inp.checked) {
                li.click();
                if (!inp.checked) inp.click();
            }
        });
    });
    checked = document.querySelectorAll('.u-questionItem input:checked').length;
    return {checked, total: qs.length};
}"""


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")


def env() -> dict:
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def ask(stem: str, opts: list[dict], multi: bool, cfg: dict) -> list[str]:
    key = cfg.get("DEEPSEEK_API_KEY", "")
    if not key:
        return []
    body = "\n".join(f"{o['letter']}. {o['text']}" for o in opts)
    kind = "多选题（通常 2~3 个正确项，不要全选）" if multi else "单选题"
    prompt = f"这是{kind}。只输出答案字母（多选连写如 ABD），不要解释。\n题干：{stem}\n{body}"
    data = json.dumps({"model": cfg.get("model", "deepseek-chat"),
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 12, "temperature": 0}).encode()
    req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=data,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            txt = json.load(resp)["choices"][0]["message"]["content"].strip().upper()
        return sorted({c for c in txt if c in "ABCDEF"})
    except Exception as exc:  # noqa: BLE001
        log(f"  llm err {str(exc)[:60]}")
        return []


def _parse() -> tuple[str, list[str]]:
    """极简参数解析：--course NAME --cids a,b,c"""
    args = sys.argv[1:]
    course = ""
    cids: list[str] = []
    for i, a in enumerate(args):
        if a == "--course" and i + 1 < len(args):
            course = args[i + 1]
        if a == "--cids" and i + 1 < len(args):
            cids = [x.strip() for x in args[i + 1].split(",") if x.strip()]
    if not cids:
        raise SystemExit("缺少 --cids（随堂测验条目的 cid，逗号分隔）。\n"
                         "提示：在课件目录里点开一条随堂测验，URL 里的 cid=xxx 就是。")
    return course, cids


def main() -> int:
    global LIST, CIDs
    course, CIDs = _parse()
    LIST = COURSES[course] if course else next(iter(COURSES.values()))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    cfg = env()
    with sync_playwright() as pw:
        b = connect(pw)
        ctx = b.contexts[0]
        tab = next((p for p in ctx.pages if "icourse163" in p.url), None) or ctx.new_page()
        for cid in CIDs:
            if state.get(cid, {}).get("ok"):
                continue
            log(f"== {cid}")
            tab.goto(LIST, wait_until="domcontentloaded", timeout=90000)
            time.sleep(6)
            for _ in range(6):
                tab.evaluate("""() => { document.querySelectorAll('.m-learnChapterNormal').forEach(ch => {
                    const box = ch.querySelector('.j-lessoBox');
                    if (!box || box.children.length === 0) { const t = ch.querySelector('.j-titleBox'); if (t) t.click(); } }); }""")
                time.sleep(2.5)
                if tab.evaluate("() => document.querySelectorAll('.sourceList > div[data-cid]').length") > 8:
                    break
            ok = tab.evaluate("""(cid) => { const el = document.querySelector('[data-cid="' + cid + '"]');
                if (!el) return 0; el.scrollIntoView({block: 'center'}); el.click(); return 1; }""", cid)
            if not ok:
                log("  click failed")
                state[cid] = {"ok": False, "error": "click"}
                STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
                continue
            time.sleep(8)
            qs = tab.evaluate(PARSE_JS)
            log(f"  questions={len(qs)}")
            ans = {}
            for q in qs:
                got = ask(q["stem"], q["opts"], q["multi"], cfg) or [q["opts"][0]["letter"]]
                ans[str(q["no"])] = got
                log(f"    Q{q['no']} -> {''.join(got)} | {q['stem'][:26]}")
            fr = tab.evaluate(FILL_JS, ans)
            log(f"  fill={fr}")
            if not isinstance(fr, dict) or fr.get("checked", 0) < max(1, len(qs) - 1):
                log("  !! 勾选不足，不提交")
                state[cid] = {"ok": False, "error": "fill", "ans": ans}
                STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
                continue
            tab.evaluate("""() => { const b = Array.from(document.querySelectorAll('a,button')).filter(e =>
                /提交/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight)); if (b.length) b[b.length-1].click(); return 1; }""")
            time.sleep(3)
            for _ in range(3):
                tab.evaluate("""() => { const b = Array.from(document.querySelectorAll('a,button,div,span')).filter(e =>
                    /^(确定|确认)$/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight));
                    if (b.length) b[b.length-1].click(); return 1; }""")
                time.sleep(3)
            t = tab.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ')") or ""
            m = re.search(r"(满分|得分|正确)[^0-9]{0,6}([\\d.]+)\\s*/\\s*([\\d.]+)", t)
            log(f"  result text: {t[-160:] if len(t) > 160 else t}")
            state[cid] = {"ok": True, "ans": ans, "score": m.group(0) if m else None,
                          "ts": datetime.now().isoformat(timespec="seconds")}
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(6)
    log("suip done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
