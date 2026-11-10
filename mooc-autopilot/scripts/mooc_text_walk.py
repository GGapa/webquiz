# -*- coding: utf-8 -*-
"""MOOC 课件——文档 + 讨论（B 线并行，用独立标签页，不干扰视频线）。

实测（2026-11-08）：
* **文档**：打开后停留约 20 秒就被记为已完成（目录里的 `learned` 变 True），不用翻页；
  保险起见会停留 18 秒，回目录核验，没成再等 20 秒重试一次。
* **讨论**：只打开**不算**完成，必须发一条回复。编辑器是 Quill（`div.ql-editor`），
  提交按钮 `a.j-replyBtn`。回复内容用 DeepSeek 按话题现写。

用法::

    python scripts/mooc_text_walk.py --limit 3
    python scripts/mooc_text_walk.py            # 全部文档+讨论
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
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

LOG = ROOT / "out" / "mooc_text_run.log"
STATE = ROOT / "out" / "mooc_text_state.json"
PLAN = ROOT / "out" / "mooc_plan.json"

EXPAND = """() => { document.querySelectorAll('.m-learnChapterNormal').forEach(ch => {
    const box = ch.querySelector('.j-lessoBox');
    if (!box || box.children.length === 0) { const t = ch.querySelector('.j-titleBox'); if (t) t.click(); } }); }"""
COUNT_ITEMS = "() => document.querySelectorAll('.sourceList > div[data-cid]').length"
LEARNED_JS = """(cid) => { const el = document.querySelector('[data-cid="' + cid + '"]');
    return el ? /\\blearned\\b/.test(el.className || '') : null; }"""


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


def ask_text(topic: str, course: str) -> str:
    cfg = env()
    key = cfg.get("DEEPSEEK_API_KEY", "")
    fallback = ("我认为算力、数据与算法是基础，人才与资本决定投入强度，产业需求提供落地场景，"
                "而治理与伦理规范决定它能不能走得远。这几者缺一不可，其中场景和人才是最难替代的。")
    if not key:
        return fallback
    prompt = (f"你是中国高校学生，正在《{course}》课程的讨论区回帖。\n"
              f"话题：{topic}\n"
              "要求：80~150 字，一段话，观点明确，结合具体例子或自身体会，口语自然，"
              "不要分点、不要标题、不要引号，直接输出回复正文。")
    data = json.dumps({"model": cfg.get("model", "deepseek-chat"),
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 400, "temperature": 0.85}).encode()
    req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=data,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            txt = json.load(resp)["choices"][0]["message"]["content"].strip()
        txt = txt.strip('"“”').replace("\n", "")
        return txt if 30 <= len(txt) <= 400 else fallback
    except Exception as exc:  # noqa: BLE001
        log(f"    llm error {str(exc)[:70]}")
        return fallback


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def open_list(tab, course: str) -> bool:
    """回目录页，滚到底把所有章节都展开，直到条目数稳定（第6、7章的条目是懒加载的）。"""
    for attempt in range(3):
        try:
            # 关键：SPA 用 hash 路由，直接 goto 同一个 URL 不会重新渲染，必须先 blank 再进
            tab.goto("about:blank", timeout=30000)
        except Exception:
            pass
        try:
            tab.goto(LIST_URL[course], wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass
        time.sleep(5)
        last = -1
        stable = 0
        for _ in range(25):
            pjs.ev(tab, EXPAND, timeout=8000)
            pjs.ev(tab, """window.scrollTo(0, document.body.scrollHeight);
                document.querySelectorAll('.j-chapterlist, .m-learnChapterList, .u-learnChapterList').forEach(e => {
                    e.scrollTop = e.scrollHeight; });
                return 1;""", timeout=6000)
            n = pjs.ev(tab, "return document.querySelectorAll('.sourceList > div[data-cid]').length;", timeout=6000) or 0
            if n == last:
                stable += 1
                if stable >= 3 and n > 10:
                    return True
            else:
                stable = 0
                last = n
            time.sleep(2)
        if last and last > 10:
            return True
        log(f"    open_list retry {attempt+1} ({course}) n={last}")
    return False


def click_item(tab, cid: str) -> bool:
    for _ in range(12):
        ok = pjs.ev(tab, """const el = document.querySelector('[data-cid="' + a.cid + '"]');
            if (!el) return 0;
            el.scrollIntoView({block: 'center'});
            el.click();
            return 1;""", {"cid": cid}, timeout=6000)
        if ok:
            return True
        tab.evaluate(EXPAND)
        time.sleep(1.2)
    return False


def is_learned(tab, cid: str):
    return pjs.ev(tab, LEARNED_JS, cid, timeout=6000)


def do_doc(tab, cid: str) -> bool:
    time.sleep(18)
    # 顺手滚一下，稳妥
    pjs.ev(tab, """window.scrollTo(0, document.body.scrollHeight);
        const els = Array.from(document.querySelectorAll('div')).filter(e => e.scrollHeight > e.clientHeight + 200);
        els.forEach(e => { e.scrollTop = e.scrollHeight; });
        return 1;""", timeout=6000)
    time.sleep(4)
    return True


def do_discussion(tab, cid: str, topic: str, course: str) -> bool:
    text = ask_text(topic, course)
    # Quill：先点编辑区再输入（直接设 innerHTML 不会触发 Quill 的 model）
    # 关键：必须用“真实点击”把焦点给 Quill 编辑器，JS click 不给焦点，键盘输入会全丢
    try:
        tab.locator("div.ql-editor").first.click(timeout=8000)
    except Exception as exc:  # noqa: BLE001
        log(f"    editor click failed {str(exc)[:60]}")
        return False
    time.sleep(0.4)
    try:
        tab.keyboard.type(text, delay=6)
    except Exception as exc:  # noqa: BLE001
        log(f"    type failed {str(exc)[:60]}")
    time.sleep(0.6)
    got = pjs.ev(tab, "return (document.querySelector('div.ql-editor')||{}).innerText || '';", timeout=6000) or ""
    if len(got.strip()) < 10:
        # 兜底：execCommand 插入
        pjs.ev(tab, """const ed = document.querySelector('div.ql-editor');
            if (!ed) return 0;
            ed.focus();
            document.execCommand('insertText', false, a.t);
            return 1;""", {"t": text}, timeout=6000)
        time.sleep(0.5)
        got = pjs.ev(tab, "return (document.querySelector('div.ql-editor')||{}).innerText || '';", timeout=6000) or ""
    log(f"    editor len={len(got.strip())}")
    if len(got.strip()) < 10:
        log("    editor still empty, skip submit")
        return False
    # 真提交是“发表回复”（a.j-edit-btn），不是“回复”（a.j-replyBtn 只是展开编辑框）
    submitted = pjs.ev(tab, """const b = document.querySelector('a.j-edit-btn') ||
            document.querySelector('a.replyBtn.j-edit-btn') || document.querySelector('a.j-replyBtn');
        if (!b) return 0;
        b.click();
        return 1;""", timeout=6000)
    time.sleep(4)
    visible = pjs.ev(tab, "return (document.body.innerText||'').includes(a.t);", {"t": text[:24]}, timeout=6000)
    log(f"    reply submit={submitted} len={len(text)} visible={visible}")
    return bool(submitted)


def main() -> int:
    args = sys.argv[1:]
    limit = 0
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
    only = next((a for a in args if a in LIST_URL), None)
    skip_disc = "--no-disc" in args
    skip_doc = "--no-doc" in args
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_state()
    done = 0
    t0 = time.time()

    with sync_playwright() as pw:
        b = connect(pw)
        ctx = b.contexts[0]
        tab = ctx.new_page()      # 独立标签，视频线继续跑
        for course in ([only] if only else list(plan)):
            todo = []
            for L in plan[course]["detail"]:
                for it in L["items"]:
                    if it["type"] in (("讨论",) if skip_doc else (("文档",) if skip_disc else ("文档", "讨论"))) and not it["learned"] \
                            and not state.get(it["cid"], {}).get("learned"):
                        todo.append(it)
            log(f"== {course}: {len(todo)} docs/discussions")
            print(f"{course}: {len(todo)}", flush=True)
            if not todo:
                continue
            if not open_list(tab, course):
                log("  open_list failed")
                continue
            for it in todo:
                if limit and done >= limit:
                    break
                cid = it["cid"]
                log(f"  [{it['type']}] {it['title'][:36]} cid={cid}")
                try:
                    if not click_item(tab, cid):
                        log("    click failed")
                        state[cid] = {"learned": False, "error": "click"}
                        save_state(state)
                        continue
                    time.sleep(5)
                    if it["type"] == "文档":
                        do_doc(tab, cid)
                    else:
                        do_discussion(tab, cid, it["title"], course)
                    open_list(tab, course)
                    lr = is_learned(tab, cid)
                    if not lr and it["type"] == "文档":
                        # 再给一次机会：多停 20 秒
                        click_item(tab, cid)
                        time.sleep(20)
                        open_list(tab, course)
                        lr = is_learned(tab, cid)
                    state[cid] = {"learned": bool(lr), "type": it["type"],
                                  "course": course, "title": it["title"],
                                  "ts": datetime.now().isoformat(timespec="seconds")}
                    save_state(state)
                    done += 1
                    log(f"    -> learned={lr} ({done})")
                except Exception as exc:  # noqa: BLE001
                    log(f"    EXCEPTION {str(exc)[:110]}")
                    state[cid] = {"learned": False, "error": str(exc)[:110],
                                  "ts": datetime.now().isoformat(timespec="seconds")}
                    save_state(state)
            if limit and done >= limit:
                break
        tab.close()
    log(f"exit: {done} items, {round(time.time()-t0)}s")
    print(f"done={done} elapsed={round(time.time()-t0)}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
