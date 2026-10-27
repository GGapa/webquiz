# -*- coding: utf-8 -*-
"""Command line interface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .browser import click_section, find_work_frame, hide_overlays, new_context
from .config import load_config
from .discover import discover
from .fill import (
    fill_homework,
    fill_quiz,
    retake_frame,
    score_from_text,
    submit_frame,
    submit_homework,
)
from .fontdecode import build_reference_matrix, decode_html
from .parse import parse_questions


def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_discover(args):
    cfg = load_config(args.config)
    discover(cfg, only=args.only, save_html=not args.no_html)


def cmd_decode(args):
    cfg = load_config(args.config)
    html_dir = Path(args.html_dir or (cfg.output_dir / "html"))
    out_dir = Path(args.out or (cfg.output_dir / "questions"))
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cfg.reference_otf.exists():
        sys.exit(
            f"reference font missing: {cfg.reference_otf}\n"
            "run: python scripts/fetch_reference_font.py"
        )
    build_reference_matrix(cfg.reference_otf, cfg.cache_file)
    count = 0
    for html_path in sorted(html_dir.glob("*.html")):
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        mapping = decode_html(html, cfg.reference_otf, cfg.cache_file)
        questions = parse_questions(html, mapping)
        tag = html_path.stem
        (out_dir / f"{tag}.questions.json").write_text(
            json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        readable = {f"U+{cp:04X}": [ch, round(sc, 3)] for cp, (ch, sc) in mapping.items()}
        (out_dir / f"{tag}.map.json").write_text(
            json.dumps(readable, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        med = sorted(sc for _, sc in mapping.values())[len(mapping) // 2] if mapping else 0
        print(f"{tag}: glyphs={len(mapping)} median={med:.3f} questions={len(questions)}")
        count += 1
    print(f"decoded {count} pages -> {out_dir}")


def _find_entry(discover_data, tag):
    for e in discover_data:
        if e.get("chapterId") == tag or Path(e.get("html", "")).stem == tag:
            return e
        if f"{e.get('index'):02d}_{e.get('chapterId')}" == tag:
            return e
    return None


def cmd_submit(args):
    from playwright.sync_api import sync_playwright

    cfg = load_config(args.config)
    if not cfg.reference_otf.exists():
        sys.exit(
            f"reference font missing: {cfg.reference_otf}\n"
            "run: python scripts/fetch_reference_font.py"
        )
    answers = _read_json(args.answers)
    answers = answers.get("answers", answers)
    q_dir = cfg.output_dir / "questions"
    questions_path = Path(args.questions) if args.questions else q_dir / f"{args.tag}.questions.json"
    questions = _read_json(questions_path)
    chapter_id = args.chapter or questions_path.stem.split("_")[1]

    with sync_playwright() as pw:
        browser, ctx = new_context(pw, cfg)
        page = ctx.new_page()
        page.goto(cfg.main_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        click_section(page, chapter_id)
        frame = find_work_frame(page, chapter_id, tries=20, interval_ms=400)
        if frame is None:
            print("no quiz frame for this section")
            browser.close()
            return
        if "selectWorkQuestionYiPiYue" in frame.url:
            if not args.retake:
                print("already submitted; pass --retake to click Redo")
                browser.close()
                return
            print("clicking Redo ...")
            retake_frame(frame, page)
            frame = find_work_frame(page, chapter_id, tries=20, interval_ms=400)
            if frame is None:
                print("could not open a new attempt")
                browser.close()
                return

        mapping = decode_html(frame.content(), cfg.reference_otf, cfg.cache_file)
        log = fill_quiz(frame, questions, answers, mapping, dry=not args.confirm)
        for item in log:
            print(item)
        if not args.confirm:
            print("dry run only; pass --confirm to submit")
        else:
            text = submit_frame(frame, page)
            print("score:", score_from_text(text) or "?")
            (cfg.output_dir / f"result_{chapter_id}.txt").write_text(text, encoding="utf-8")
        browser.close()


def cmd_homework(args):
    from playwright.sync_api import sync_playwright

    cfg = load_config(args.config)
    answers = _read_json(args.answers)
    answers = answers.get("answers", answers)
    url = args.url or cfg.main_url

    with sync_playwright() as pw:
        browser, ctx = new_context(pw, cfg)
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        hide_overlays(page)
        html = page.content()
        questions = parse_questions(html, {})
        if not questions:
            print("no questions parsed; is this a dowork page?")
            browser.close()
            return
        log = fill_homework(page, questions, answers, {}, dry=not args.confirm)
        for item in log:
            print(item)
        if not args.confirm:
            print("dry run only; pass --confirm to submit (usually one attempt)")
        else:
            text = submit_homework(page)
            print("score:", score_from_text(text) or "?")
            (cfg.output_dir / "homework_result.txt").write_text(text, encoding="utf-8")
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="webquiz", description="Chaoxing quiz/homework helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("discover", help="list sections and detect quizzes")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--only", nargs="*", help="only these chapterIds")
    p.add_argument("--no-html", action="store_true")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("decode", help="decode saved HTML pages into questions JSON")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--html-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("submit", help="fill one quiz; add --confirm to submit")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--tag", required=True, help="e.g. 02_<chapterId>")
    p.add_argument("--chapter")
    p.add_argument("--questions")
    p.add_argument("--answers", required=True)
    p.add_argument("--retake", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("homework", help="fill a mooc2/work/dowork homework")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--url")
    p.add_argument("--answers", required=True)
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_homework)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
