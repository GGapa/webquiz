# -*- coding: utf-8 -*-
"""统一入口：python -m mooc <子命令>

每个子命令对应 scripts/ 下的一个驱动脚本。这里只做参数映射，
真正的逻辑在各脚本里（也可以单独 `python scripts/xxx.py` 跑）。

    python -m mooc plan                       生成课程清单
    python -m mooc video --limit 2            刷视频
    python -m mooc text --docs-only           只做文档
    python -m mooc text --discuss-only        只发讨论
    python -m mooc quiz --url <URL> --tag 第1章
    python -m mooc suip --cids 123,456
    python -m mooc hw --url <URL> --answers a.json --submit
    python -m mooc quiz-list                  枚举测验 id
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def run_script(script: str, argv: list[str]) -> int:
    """用子进程跑 scripts/ 下的脚本，保持和直接运行完全一致的行为。"""
    cmd = [sys.executable, str(SCRIPTS / script), *argv]
    return subprocess.call(cmd, cwd=str(REPO))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mooc", description="中国大学MOOC 批量操作（视频/文档/讨论/测验/作业）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan", help="生成课程条目清单 out/mooc_plan.json")

    p = sub.add_parser("video", help="批量播放视频（2 倍速）")
    p.add_argument("--course", help="只做某一门课（config.yaml 里的课程名）")
    p.add_argument("--limit", type=int, default=0, help="本次最多做几段")

    p = sub.add_parser("text", help="文档打卡 / 讨论发帖")
    p.add_argument("--course", help="只做某一门课")
    p.add_argument("--limit", type=int, default=0)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--docs-only", action="store_true", help="只做文档")
    g.add_argument("--discuss-only", action="store_true", help="只发讨论")

    p = sub.add_parser("quiz", help="做一份单元测验")
    p.add_argument("--url", required=True, help="测验页面 URL（含 /quiz?id=）")
    p.add_argument("--tag", default="quiz", help="结果文件名标签")
    p.add_argument("--votes", type=int, default=1, help="每题问几次模型取多数（默认 1）")

    p = sub.add_parser("suip", help="做课件里的随堂测验")
    p.add_argument("--cids", required=True, help="随堂测验条目 cid，逗号分隔")
    p.add_argument("--course", help="课程名")

    p = sub.add_parser("hw", help="交作业（文本 + 可选附件）")
    p.add_argument("--url", required=True)
    p.add_argument("--answers", required=True, help="答案 JSON 路径")
    p.add_argument("--submit", action="store_true", help="真正提交（不加只填写）")

    sub.add_parser("quiz-list", help="枚举每门课的测验 id")

    p = sub.add_parser("doctor", help="环境自检（--fix 自动修复）")
    p.add_argument("--fix", action="store_true", help="自动修复能修的问题")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "doctor":
        from .doctor import main as doctor_main
        return doctor_main([*(["--fix"] if args.fix else []), *(["--json"] if args.json else [])])

    if args.cmd == "plan":
        return run_script("mooc_refresh_plan.py", [])
    if args.cmd == "quiz-list":
        return run_script("mooc_quiz_list.py", [])

    if args.cmd == "video":
        extra = []
        if args.course:
            extra.append(args.course)
        if args.limit:
            extra += ["--limit", str(args.limit)]
        return run_script("mooc_video_walk.py", extra)

    if args.cmd == "text":
        extra = []
        if args.course:
            extra.append(args.course)
        if args.limit:
            extra += ["--limit", str(args.limit)]
        if args.docs_only:
            extra.append("--no-disc")
        if args.discuss_only:
            extra.append("--no-doc")
        return run_script("mooc_text_walk.py", extra)

    if args.cmd == "quiz":
        return run_script("mooc_quiz_do.py",
                          [args.tag, args.url, "--votes", str(args.votes)])

    if args.cmd == "suip":
        extra = ["--cids", args.cids]
        if args.course:
            extra += ["--course", args.course]
        return run_script("mooc_suip.py", extra)

    if args.cmd == "hw":
        extra = ["--url", args.url, "--answer-file", args.answers]
        if args.submit:
            extra.append("--submit")
        return run_script("mooc_hw_fill.py", extra)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
