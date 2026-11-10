# -*- coding: utf-8 -*-
"""MOOC 课件——视频批量播放器（A 线，先跑这个，因为最耗时）。

2026-11-08 实测要点：
* 课件条目可以直接点开（`[data-cid=...]`），点开后 URL 形如
  `#/learn/content?type=detail&id=<lessonId>&cid=<cid>`；
* **2 倍速有效**：513 秒的视频用 250 秒播完，目录里的 `learned` 标记照样变 True；
* 播放器就是普通 `<video>`，`playbackRate=2` 直接用，不用碰播放器 UI；
* 完成状态看目录条目的 class 里有没有 `learned`。

用法::

    python scripts/mooc_video_walk.py            # 跑全部三门课没看完的视频
    python scripts/mooc_video_walk.py --limit 2  # 只跑两条（验证用）
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sys
import time
import traceback

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

LOG = ROOT / "out" / "mooc_video_run.log"
PLAN = ROOT / "out" / "mooc_plan.json"
STATE = ROOT / "out" / "mooc_video_state.json"


EXPAND = """() => { document.querySelectorAll('.m-learnChapterNormal').forEach(ch => {
    const box = ch.querySelector('.j-lessoBox');
    if (!box || box.children.length === 0) { const t = ch.querySelector('.j-titleBox'); if (t) t.click(); } }); }"""

READ_ITEMS = """() => {
    const out = [];
    document.querySelectorAll('.sourceList > div[data-cid]').forEach(d => {
        const tagEl = d.querySelector('.tag');
        out.push({cid: d.getAttribute('data-cid'),
                  type: (tagEl ? tagEl.innerText : '').trim(),
                  title: (d.getAttribute('title') || '').slice(0, 50),
                  learned: /\\blearned\\b/.test(d.className || '')});
    });
    return out;
}"""


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def open_list(page, course: str) -> bool:
    """回目录页，滚到底把所有章节都展开，直到条目数稳定（第6、7章的条目是懒加载的）。"""
    for attempt in range(3):
        try:
            # 关键：SPA 用 hash 路由，直接 goto 同一个 URL 不会重新渲染，必须先 blank 再进
            page.goto("about:blank", timeout=30000)
        except Exception:
            pass
        try:
            page.goto(LIST_URL[course], wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass
        time.sleep(5)
        last = -1
        stable = 0
        for _ in range(25):
            pjs.ev(page, EXPAND, timeout=8000)
            pjs.ev(page, """window.scrollTo(0, document.body.scrollHeight);
                document.querySelectorAll('.j-chapterlist, .m-learnChapterList, .u-learnChapterList').forEach(e => {
                    e.scrollTop = e.scrollHeight; });
                return 1;""", timeout=6000)
            n = pjs.ev(page, "return document.querySelectorAll('.sourceList > div[data-cid]').length;", timeout=6000) or 0
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


def click_item(page, cid: str) -> bool:
    """点开一条课件。SPA 的目录树会晚渲染，所以要轮询等元素出现。"""
    for attempt in range(3):
        for _ in range(15):
            ok = pjs.ev(page, """const el = document.querySelector('[data-cid="' + a.cid + '"]');
                if (!el) return 0;
                el.scrollIntoView({block: 'center'});
                el.click();
                return 1;""", {"cid": cid}, timeout=6000)
            if ok:
                return True
            pjs.ev(page, EXPAND, timeout=6000)
            time.sleep(1.5)
        time.sleep(2)
    return False


def item_learned(page, cid: str):
    got = pjs.ev(page, """const el = document.querySelector('[data-cid="' + a.cid + '"]');
        if (!el) return null;
        return /\\blearned\\b/.test(el.className || '');""", {"cid": cid}, timeout=8000)
    return got


def play_video(page, hard_limit: float = 3600.0) -> dict:
    """把当前视频页面播到结尾（2 倍速）。"""
    t0 = time.time()
    time.sleep(3)
    st = pjs.ev(page, """const v = document.querySelector('video');
        if (!v) return null;
        v.muted = true; v.playbackRate = 2; v.play().catch(()=>{});
        return {d: v.duration || 0};""", timeout=8000)
    if not st:
        return {"error": "no-video"}
    dur = float(st.get("d") or 0)
    log(f"    video dur={dur:.0f}s")
    last = -1
    stall = 0
    while time.time() - t0 < min(hard_limit, dur / 2 + 300):
        time.sleep(8)
        v = pjs.ev(page, """const v = document.querySelector('video');
            return v ? {t: v.currentTime || 0, d: v.duration || 0, e: !!v.ended, p: !!v.paused} : null;""",
            timeout=6000)
        if not v:
            break
        if v["e"] or (v["d"] and v["t"] >= v["d"] - 1):
            await_end = time.time()
            time.sleep(6)   # 等它把进度上报完
            log(f"    ended at {v['t']:.0f}/{v['d']:.0f}s wall={round(time.time()-t0)}s")
            return {"dur": round(v["d"]), "wall": round(time.time() - t0)}
        if v["p"]:
            pjs.ev(page, """const v = document.querySelector('video');
                if (v) { v.muted = true; v.playbackRate = 2; v.play().catch(()=>{}); } return 1;""", timeout=6000)
            stall += 1
        if v["t"] - last < 4:
            stall += 1
            if stall >= 3:
                pjs.ev(page, """const v = document.querySelector('video');
                    if (v) { v.muted = true; v.playbackRate = 2; v.play().catch(()=>{}); } return 1;""", timeout=6000)
                stall = 0
        else:
            stall = 0
        if v["t"] - last >= 60:
            log(f"      {v['t']:.0f}/{v['d']:.0f}s")
        last = v["t"]
    return {"dur": round(dur), "wall": round(time.time() - t0), "timeout": True}


def main() -> int:
    args = sys.argv[1:]
    limit = 0
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
    only = next((a for a in args if a in LIST_URL), None)

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_state()
    done = 0
    t_start = time.time()

    with sync_playwright() as pw:
        b = connect(pw)
        ctx = b.contexts[0]
        page = next((p for p in ctx.pages if "icourse163" in p.url), None) or ctx.new_page()

        courses = [only] if only else list(plan)
        for course in courses:
            items = plan[course]["detail"]
            pending = []
            for L in items:
                for it in L["items"]:
                    if it["type"] == "视频" and not it["learned"]:
                        pending.append({"lesson": L["lesson"], "cid": it["cid"], "title": it["title"]})
            log(f"== {course}: {len(pending)} videos pending")
            print(f"{course}: {len(pending)} videos", flush=True)
            if not pending:
                continue
            open_list(page, course)
            for it in pending:
                cid = it["cid"]
                if limit and done >= limit:
                    break
                if state.get(cid, {}).get("learned"):
                    continue
                log(f"  [{course}] {it['title'][:34]} cid={cid}")
                try:
                    if not click_item(page, cid):
                        log("    click failed")
                        state[cid] = {"learned": False, "error": "click"}
                        save_state(state)
                        continue
                    time.sleep(6)
                    r = play_video(page)
                    # 回目录核验
                    open_list(page, course)
                    lr = item_learned(page, cid)
                    state[cid] = {**r, "learned": bool(lr), "course": course,
                                  "title": it["title"], "ts": datetime.now().isoformat(timespec="seconds")}
                    save_state(state)
                    done += 1
                    log(f"    -> learned={lr} {r} ({done})")
                except Exception as exc:  # noqa: BLE001
                    log(f"    EXCEPTION {str(exc)[:120]}")
                    log("    " + " | ".join(traceback.format_exc().splitlines()[-3:]))
                    state[cid] = {"learned": False, "error": str(exc)[:120],
                                  "ts": datetime.now().isoformat(timespec="seconds")}
                    save_state(state)
                    try:
                        open_list(page, course)
                    except Exception:  # noqa: BLE001
                        pass
            if limit and done >= limit:
                break

    log(f"exit: {done} videos, {round(time.time()-t_start)}s")
    print(f"done={done} elapsed={round(time.time()-t_start)}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
