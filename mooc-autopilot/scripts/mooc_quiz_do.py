# -*- coding: utf-8 -*-
"""MOOC 单元测验：解析 → 模型作答 → 勾选 → 提交 → 读分（单次作答）。

DOM 结构（2026-11-08 实测）：
  题目块  `.u-questionItem`（.m-choiceQuestion）
  题干    `.j-title .j-richTxt`
  题型    `.qaCate span`（单选/多选/判断）
  选项    `.j-choicebox ul.choices li` → `input[type=radio|checkbox]` + `label .optionPos`（A.）/.optionCnt

用时限制 15 分钟，所以默认每题只问 1 次（temperature 0），要更准可 `--votes 3`。
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


ROOT = Path(__file__).resolve().parents[1]


import pjs  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

LOG = ROOT / "out" / "mooc_quiz_run.log"
OUT = ROOT / "out" / "mooc_quiz_state.json"


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


PARSE_JS = """() => {
    const qs = Array.from(document.querySelectorAll('.u-questionItem'));
    return qs.map((q, i) => {
        const cat = (q.querySelector('.qaCate') || {}).innerText || '';
        const stem = ((q.querySelector('.j-richTxt') || {}).innerText || '').replace(/\\s+/g, ' ').trim();
        const opts = [];
        q.querySelectorAll('.j-choicebox ul.choices > li').forEach(li => {
            const pos = ((li.querySelector('.optionPos') || {}).innerText || '').trim().replace('.', '');
            const txt = ((li.querySelector('.optionCnt') || {}).innerText || '').replace(/\\s+/g, ' ').trim();
            const inp = li.querySelector('input');
            opts.push({letter: pos, text: txt, inId: inp ? inp.id : ''});
        });
        return {no: i + 1, cat: cat.replace(/\\s+/g, ' ').trim(), stem, opts,
                multi: /多选/.test(cat)};
    });
}"""

FILL_JS = """(ans) => {
    const qs = Array.from(document.querySelectorAll('.u-questionItem'));
    let filled = 0;
    qs.forEach((q, i) => {
        const want = ans[String(i + 1)] || [];
        if (!want.length) return;
        const lis = Array.from(q.querySelectorAll('.j-choicebox ul.choices > li'));
        lis.forEach(li => {
            const pos = ((li.querySelector('.optionPos') || {}).innerText || '').trim().replace('.', '');
            const inp = li.querySelector('input');
            if (!inp) return;
            const wantIt = want.indexOf(pos) >= 0;
            if (wantIt && !inp.checked) {
                li.click();
                if (!inp.checked) { inp.click(); }
                if (!inp.checked) {
                    const lab = li.querySelector('label');
                    if (lab) lab.click();
                }
                if (inp.checked) filled++;
            }
        });
    });
    const checked = document.querySelectorAll('.u-questionItem input:checked').length;
    return {filled, checked, total: qs.length};
}"""

def ask(stem: str, opts: list[dict], multi: bool, votes: int, cfg: dict) -> list[str]:
    key = cfg.get("DEEPSEEK_API_KEY", "")
    if not key:
        return []
    body = "\n".join(f"{o['letter']}. {o['text']}" for o in opts)
    kind = "多选题（通常 2~3 个正确项，除非确实全对，不要全选）" if multi else "单选题"
    prompt = (f"这是{kind}。先在心里逐项判断，最后只输出答案字母（多选连写如 ABD），不要解释。\n"
              f"题干：{stem}\n{body}")
    results = []
    for i in range(max(1, votes)):
        data = json.dumps({"model": cfg.get("model", "deepseek-chat"),
                           "messages": [{"role": "user", "content": prompt}],
                           "max_tokens": 16, "temperature": 0.0 if i == 0 else 0.6}).encode()
        req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=data,
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                txt = json.load(resp)["choices"][0]["message"]["content"].strip().upper()
            letters = sorted({c for c in txt if c in "ABCDEF"})
            if letters:
                results.append(tuple(letters))
        except Exception as exc:  # noqa: BLE001
            log(f"  llm err {str(exc)[:60]}")
    if not results:
        return []
    from collections import Counter
    return list(Counter(results).most_common(1)[0][0])


def main() -> int:
    args = sys.argv[1:]
    votes = 1
    for i, a in enumerate(args):
        if a == "--votes" and i + 1 < len(args):
            votes = int(args[i + 1])
    tag = next((a for a in args if not a.startswith("-") and not a.isdigit()), "quiz")

    with sync_playwright() as pw:
        b = connect(pw)
        ctx = b.contexts[0]
        url = next((a for a in args if a.startswith("http")), None)
        tab = next((p for p in ctx.pages if "/quiz?id=" in p.url), None)
        if tab is None:
            tab = next((p for p in ctx.pages if "icourse163" in p.url), None)
        if tab is None:
            tab = ctx.new_page()
        if url:
            tab.goto(url, wait_until="domcontentloaded", timeout=90000)
            time.sleep(8)
        if tab is None:
            print("no quiz tab"); return 1
        # 已考过：先点“再做一次”开新的一次作答
        again = tab.evaluate("""() => {
            const a = Array.from(document.querySelectorAll('a,button,span,div')).find(e =>
                /再做一次|再测一次/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight));
            if (!a) return 0;
            a.click();
            return 1; }""")
        if again:
            log("clicked 再做一次")
            time.sleep(6)
        # 如果是测验介绍页，先勾选诚信承诺并开始
        if tab.evaluate("() => !!document.querySelector('a.j-startBtn')"):
            tab.evaluate("""() => {
                const cb = document.querySelector('input.j-agree') || document.querySelector('input[type=checkbox]');
                if (cb && !cb.checked) cb.click();
                return 1; }""")
            time.sleep(1)
            tab.evaluate("() => { const b=document.querySelector('a.j-startBtn'); if (b) b.click(); return 1; }")
            time.sleep(6)
            log("started quiz")
        qs = tab.evaluate(PARSE_JS)
        log(f"== {tag}: {len(qs)} questions")
        print(f"questions: {len(qs)}")
        if not qs:
            return 1
        cfg = env()
        ans = {}
        for q in qs:
            got = ask(q["stem"], q["opts"], q["multi"], votes, cfg)
            if not got:
                got = [q["opts"][0]["letter"]] if q["opts"] else []
            ans[str(q["no"])] = got
            log(f"  Q{q['no']} {q['cat']} -> {''.join(got)}")
        (ROOT / "out" / f"quiz_answers_mooc_{tag}.json").write_text(
            json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
        fr = tab.evaluate(FILL_JS, ans)
        log(f"fill result={fr}")
        print("fill:", fr)
        if not isinstance(fr, dict) or fr.get("checked", 0) < max(1, len(qs) - 3):
            log("!! too few checked, abort before submit")
            print("ABORT: answers not registered")
            return 2
        time.sleep(1)
        # 提交
        subm = tab.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a,button')).filter(e =>
                /提交/.test((e.innerText||'').trim()) && (e.offsetWidth||e.offsetHeight));
            if (!btns.length) return 0;
            btns[btns.length - 1].click();
            return 1; }""")
        log(f"submit click={subm}")
        time.sleep(3)
        # 确认弹窗
        for _ in range(4):
            ok = tab.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('a,button,div,span')).filter(e => {
                    const t=(e.innerText||'').trim();
                    return /^(确定|确认|提交|是)$/.test(t) && (e.offsetWidth||e.offsetHeight);
                });
                if (btns.length) { btns[btns.length-1].click(); return 1; }
                return 0; }""")
            if ok:
                log("confirm clicked")
            time.sleep(3)
            txt = tab.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ')")
            if "得分" in txt or "成绩" in txt:
                break
        time.sleep(5)
        txt = tab.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ')")
        m = re.search(r"本次得分为[：:]?\s*([\d.]+)\s*/\s*([\d.]+)", txt)
        if not m:
            m = re.search(r"(?:得分|成绩)[:：]?\s*([\d.]+)\s*/\s*([\d.]+)", txt)
        score = (m.group(1) + "/" + m.group(2)) if m else None
        st = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        st[tag] = {"score": score, "answers": ans, "ts": datetime.now().isoformat(timespec="seconds")}
        OUT.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"score={score}")
        print("score:", score)
        print("text:", txt[:300])
        # 收尾：标签重置 + 把窗口压回最小化（绝不能弹到用户前面）
        try:
            tab.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        try:
            cdp = ctx.new_cdp_session(tab)
            wid = cdp.send("Browser.getWindowForTarget")["windowId"]
            cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "minimized"}})
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
