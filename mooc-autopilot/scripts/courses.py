# -*- coding: utf-8 -*-
"""课程列表：从 config.yaml 的 icourse163.courses 读取（name -> 课程内容页 URL）。

在 config.yaml 里这样写：

    icourse163:
      courses:
        我的课程A: "https://www.icourse163.org/learn/XXX-1234567#/learn/content"
        我的课程B: "https://www.icourse163.org/spoc/learn/XXX-7654321#/learn/content"

也可以用环境变量 MOOC_COURSES 传 JSON：{"课程名": "url"}

`COURSES` 是**惰性加载**的：只有真正用到时才去读 config.yaml，
所以 `python scripts/xxx.py --help` 在没有配置文件时也能正常工作。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_ENV = "MOOC_CONFIG"


def _config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV, "config.yaml"))


def load_courses(config_path: str | Path | None = None) -> dict[str, str]:
    env = os.environ.get("MOOC_COURSES")
    if env:
        return json.loads(env)
    p = Path(config_path) if config_path else _config_path()
    if not p.exists():
        raise SystemExit(
            f"找不到 {p}。请把 config.example.yaml 复制成 config.yaml，"
            "并在 icourse163.courses 里填上你的课程链接（课程名 -> #/learn/content 链接）。"
        )
    try:
        import yaml
    except ImportError:
        raise SystemExit("缺少依赖 PyYAML：pip install -r requirements.txt")
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    courses = ((raw.get("icourse163") or {}).get("courses")) or {}
    courses = {k: v for k, v in courses.items() if not str(k).startswith(("示例", "example"))}
    if not courses:
        raise SystemExit(
            "config.yaml 里 icourse163.courses 是空的（或只有示例项）。"
            "请填成：课程名: \"https://www.icourse163.org/learn/XXX-123#/learn/content\""
        )
    return {str(k): str(v) for k, v in courses.items()}


class _LazyCourses(dict):
    """第一次访问时才读配置，避免 --help 也要求配置文件。"""

    def _ensure(self) -> None:
        if not self:
            super().update(load_courses())

    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)

    def __iter__(self):
        self._ensure()
        return super().__iter__()

    def __len__(self):
        self._ensure()
        return super().__len__()

    def items(self):
        self._ensure()
        return super().items()

    def keys(self):
        self._ensure()
        return super().keys()

    def values(self):
        self._ensure()
        return super().values()

    def get(self, key, default=None):
        self._ensure()
        return super().get(key, default)

    def __contains__(self, key):
        self._ensure()
        return super().__contains__(key)


COURSES = _LazyCourses()
