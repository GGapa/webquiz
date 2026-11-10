# -*- coding: utf-8 -*-
"""共享的运行环境设置：仓库根目录、输出目录、CDP 地址。

优先级：环境变量 > config.yaml > 默认值。
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / os.environ.get("MOOC_OUT", "out")
CONFIG_PATH = Path(os.environ.get("MOOC_CONFIG", REPO_ROOT / "config.yaml"))


def _from_config(key_path: list[str]):
    try:
        import yaml
    except ImportError:
        return None
    if not CONFIG_PATH.exists():
        return None
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    cur = raw
    for k in key_path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


CDP_URL: str = (
    os.environ.get("CDP_URL")
    or _from_config(["browser", "cdp_url"])
    or "http://127.0.0.1:9222"
)

# 各驱动脚本用这个名字
CDP: str = CDP_URL

# 大模型（可选）
LLM_KEY_ENV = "DEEPSEEK_API_KEY"
LLM_MODEL = os.environ.get("LLM_MODEL") or _from_config(["llm", "model"]) or "deepseek-chat"
LLM_URL = _from_config(["llm", "base_url"]) or "https://api.deepseek.com/chat/completions"


def ensure_out() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


def connect(pw):
    """连接已登录的浏览器；失败时给可操作的提示，而不是抛一堆 traceback。"""
    try:
        return pw.chromium.connect_over_cdp(CDP_URL)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"连不上浏览器（{CDP_URL}）：{str(exc)[:120]}\n\n"
            "请先启动一个带调试端口的 Chrome/Edge，并在里面登录好课程：\n"
            '  msedge.exe --remote-debugging-port=9222 --user-data-dir=C:\\edge-debug ^\n'
            "    --disable-background-timer-throttling --mute-audio\n\n"
            "端口不是 9222 的话，用环境变量 CDP_URL 或 config.yaml 的 browser.cdp_url 指定。"
        )
