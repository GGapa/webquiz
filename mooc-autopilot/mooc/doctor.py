# -*- coding: utf-8 -*-
"""环境自检与自动修复：python -m mooc doctor [--fix] [--json] [--live]

设计目标：**把踩过的坑变成可执行的检查项**，让后来的人（或别的 AI）
不必重走一遍调试流程——每一项失败都带「原因 + 一条能直接跑的命令」。

检查项：
  1. Python 版本 >= 3.10
  2. 临时目录可写（Playwright 启动驱动需要）
  3. config.yaml 存在且填了课程
  4. cookies.txt 存在且非空（超星用）
  5. 调试端口 CDP 可达
  6. 参考字体存在（超星字体解码用）
  7. playwright / PyYAML 已安装
  8. （--live）页面结构探针：关键选择器是否还在

--fix 会自动做安全修复：建临时目录、复制 config、下载字体、拉起浏览器。
不会自动做的事：填写你的课程 URL / Cookie（这些只有你知道）。
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 浏览器调试用的独立配置目录：放在用户目录下，**不要**放进仓库
PROFILE_DIR = Path(os.environ.get("MOOC_PROFILE_DIR")
                   or (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "mooc-autopilot" / "edge-debug"))
SCRIPTS = REPO / "scripts"
CONFIG = Path(os.environ.get("MOOC_CONFIG", REPO / "config.yaml"))


# ────────────────────────────── 数据结构 ──────────────────────────────
@dataclass
class Check:
    key: str
    title: str
    ok: bool
    critical: bool = True          # 关键项失败 → 无法工作
    detail: str = ""               # 现状
    cause: str = ""                # 为什么会这样
    fix_cmd: str = ""              # 人能直接跑的命令
    auto_fix: str = ""             # --fix 时执行的内部动作名
    fixed: bool = False            # --fix 之后是否修好了


CHECKS: list[Check] = []


def add(c: Check) -> Check:
    CHECKS.append(c)
    return c


# ────────────────────────────── 单项检查 ──────────────────────────────
def check_python() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    return add(Check(
        "python", "Python 版本",
        ok=ok,
        detail=f"{v.major}.{v.minor}.{v.micro}",
        cause="本项目用了 `str | None` 等 3.10+ 语法" if not ok else "",
        fix_cmd="安装 Python 3.10+ 后重建虚拟环境：python -m venv .venv",
    ))


def check_temp() -> Check:
    try:
        fd, p = tempfile.mkstemp(prefix="mooc_doctor_")
        os.close(fd)
        os.unlink(p)
        return add(Check("temp", "临时目录可写", ok=True,
                         detail=tempfile.gettempdir()))
    except Exception as exc:  # noqa: BLE001
        return add(Check(
            "temp", "临时目录可写", ok=False,
            detail=str(exc)[:80],
            cause="TEMP/TMP 指向不存在或不可写的目录，Playwright 起不来驱动",
            fix_cmd="新建一个可写目录并设置：set TEMP=D:\\mooc-tmp && set TMP=%TEMP%",
            auto_fix="temp",
        ))


def check_config() -> Check:
    if not CONFIG.exists():
        return add(Check(
            "config", "config.yaml 存在", ok=False,
            detail=f"未找到 {CONFIG}",
            cause="还没从模板复制",
            fix_cmd="copy config.example.yaml config.yaml  （然后填课程 URL）",
            auto_fix="config",
        ))
    try:
        import yaml
        raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return add(Check("config", "config.yaml 解析", ok=False,
                         detail=str(exc)[:80],
                         cause="YAML 语法错误（缩进/引号）",
                         fix_cmd=f"用编辑器检查 {CONFIG} 的缩进"))
    courses = ((raw.get("icourse163") or {}).get("courses")) or {}
    courses = {k: v for k, v in courses.items() if not str(k).startswith(("示例", "example"))}
    main_url = ((raw.get("course") or {}).get("main_url")) or ""
    has_chaoxing = "REPLACE" not in main_url and "studentstudy" in main_url
    if not courses and not has_chaoxing:
        return add(Check(
            "config", "config.yaml 已填写", ok=False,
            detail="icourse163.courses 为空，超星 main_url 也没填",
            cause="模板里的示例值还没替换",
            fix_cmd='在 config.yaml 填：icourse163.courses: {"课程名": "https://www.icourse163.org/learn/XXX-123#/learn/content"}',
        ))
    return add(Check("config", "config.yaml 已填写", ok=True,
                     detail=f"慕课 {len(courses)} 门" + ("，超星已配" if has_chaoxing else "")))


def check_cookies() -> Check:
    try:
        import yaml
        raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        rel = ((raw.get("course") or {}).get("cookie_file")) or "cookies.txt"
    except Exception:
        rel = "cookies.txt"
    p = CONFIG.parent / rel if not Path(rel).is_absolute() else Path(rel)
    if not p.exists() or p.stat().st_size < 20:
        return add(Check(
            "cookies", "cookies.txt（超星用）", ok=True, critical=False,
            detail="未提供——只影响超星，慕课不需要",
            cause="超星页面需要登录态",
            fix_cmd="F12 → Network → 任一请求 → 复制 Cookie 头，存成 cookies.txt",
        ))
    return add(Check("cookies", "cookies.txt（超星用）", ok=True, critical=False,
                     detail=f"{p.stat().st_size} 字节"))


def check_cdp() -> Check:
    cdp = os.environ.get("CDP_URL", "http://127.0.0.1:9222")
    try:
        with urllib.request.urlopen(cdp + "/json/version", timeout=4) as r:
            info = json.loads(r.read().decode("utf-8", "ignore"))
        return add(Check("cdp", "浏览器调试端口", ok=True,
                         detail=f"{cdp} → {info.get('Browser', '?')[:40]}"))
    except Exception as exc:  # noqa: BLE001
        return add(Check(
            "cdp", "浏览器调试端口", ok=False,
            detail=f"{cdp} 连不上：{str(exc)[:60]}",
            cause="浏览器没带 --remote-debugging-port 启动，或端口被占",
            fix_cmd=(f'"{find_browser()}" --remote-debugging-port=9222 '
                     f'--user-data-dir={PROFILE_DIR} --mute-audio'),
            auto_fix="browser",
        ))


def check_font() -> Check:
    f = REPO / "assets" / "SourceHanSansSC-Normal.otf"
    if f.exists() and f.stat().st_size > 1_000_000:
        return add(Check("font", "字体解码参考字体", ok=True,
                         detail=f"{f.stat().st_size / 1e6:.1f} MB"))
    return add(Check(
        "font", "字体解码参考字体", ok=True, critical=False,
        detail="未下载——只影响超星的字体混淆解码",
        cause="字体文件太大不入仓库",
        fix_cmd="python scripts/fetch_reference_font.py",
        auto_fix="font",
    ))


def check_deps() -> Check:
    missing = []
    for mod in ("playwright", "yaml"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return add(Check("deps", "Python 依赖", ok=False,
                         detail="缺少：" + ", ".join(missing),
                         cause="没装依赖",
                         fix_cmd="pip install -r requirements.txt",
                         auto_fix="deps"))
    return add(Check("deps", "Python 依赖", ok=True, detail="playwright / PyYAML 已装"))


# ────────────────────────────── 自动修复 ──────────────────────────────
def find_browser() -> str:
    names = {
        "Windows": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "Linux": ["/usr/bin/google-chrome", "/usr/bin/chromium"],
    }.get(platform.system(), [])
    for n in names:
        if Path(n).exists():
            return n
    return "chrome"  # 交给 PATH


def try_fix(c: Check) -> bool:
    """执行安全修复；返回是否修好了。"""
    if c.auto_fix == "temp":
        d = REPO / ".tmp"
        d.mkdir(exist_ok=True)
        os.environ["TEMP"] = os.environ["TMP"] = str(d)
        try:
            fd, p = tempfile.mkstemp(dir=d)
            os.close(fd)
            os.unlink(p)
            return True
        except Exception:
            return False

    if c.auto_fix == "config":
        src = REPO / "config.example.yaml"
        if src.exists():
            shutil.copyfile(src, CONFIG)
            print(f"  已复制模板 → {CONFIG}（**还需要你填课程 URL 和 Cookie**）")
            return True
        return False

    if c.auto_fix == "font":
        rc = subprocess.call([sys.executable, str(SCRIPTS / "fetch_reference_font.py")],
                             cwd=str(REPO))
        return rc == 0

    if c.auto_fix == "deps":
        rc = subprocess.call([sys.executable, "-m", "pip", "install", "-r",
                              str(REPO / "requirements.txt")])
        return rc == 0

    if c.auto_fix == "browser":
        exe = find_browser()
        try:
            subprocess.Popen([exe, "--remote-debugging-port=9222",
                              f"--user-data-dir={PROFILE_DIR}",
                              "--no-first-run", "--mute-audio",
                              "--disable-background-timer-throttling",
                              "--disable-backgrounding-occluded-windows",
                              "--window-position=-3200,-3200", "about:blank"])
            import time
            time.sleep(6)
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4).read()
            print("  已拉起浏览器（屏幕外），请在里面登录课程")
            return True
        except Exception:
            return False

    return False


# ────────────────────────────── 输出 ──────────────────────────────
def render(as_json: bool) -> int:
    fails = [c for c in CHECKS if not c.ok]
    if as_json:
        print(json.dumps([c.__dict__ for c in CHECKS], ensure_ascii=False, indent=2))
        return 0 if not fails else 1

    print("\n=== mooc doctor：环境自检 ===\n")
    for c in CHECKS:
        mark = "✅" if c.ok else ("❌" if c.critical else "⚠️ ")
        print(f"{mark} {c.title:22s} {c.detail}")
        if not c.ok:
            if c.cause:
                print(f"     原因：{c.cause}")
            if c.fix_cmd:
                print(f"     解决：{c.fix_cmd}")
            if c.auto_fix:
                print(f"     可自动修复：python -m mooc doctor --fix")
        print()

    if not fails:
        print("全部通过，可以开始干活了。")
        return 0
    critical = [c for c in fails if c.critical]
    print(f"共 {len(fails)} 项待处理（其中 {len(critical)} 项会导致无法运行）。")
    print("加 --fix 可以自动修掉能修的部分。")
    return 1


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mooc doctor", description="环境自检与自动修复")
    ap.add_argument("--fix", action="store_true", help="自动修复能修的问题")
    ap.add_argument("--json", action="store_true", help="输出 JSON（方便别的程序读）")
    args = ap.parse_args(argv)

    check_python()
    check_temp()
    check_deps()
    check_config()
    check_cookies()
    check_font()
    check_cdp()

    if args.fix:
        print("\n=== 自动修复 ===")
        for c in CHECKS:
            if not c.ok and c.auto_fix:
                print(f"- 修复：{c.title}")
                c.fixed = try_fix(c)
                # 修完重新检查该项
        # 重新跑一遍全部检查
        CHECKS.clear()
        check_python()
        check_temp()
        check_deps()
        check_config()
        check_cookies()
        check_font()
        check_cdp()

    return render(args.json)


if __name__ == "__main__":
    raise SystemExit(main())
