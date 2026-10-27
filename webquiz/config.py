# -*- coding: utf-8 -*-
"""Configuration loading."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    path: Path
    raw: dict[str, Any]

    @property
    def base_dir(self) -> Path:
        return self.path.parent

    def resolve(self, value: str | Path) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (self.base_dir / p)

    @property
    def main_url(self) -> str:
        url = self.raw["course"]["main_url"].strip()
        if "REPLACE" in url:
            raise ValueError("config: course.main_url still contains REPLACE placeholder")
        return url

    @property
    def cookie_file(self) -> Path:
        return self.resolve(self.raw["course"].get("cookie_file", "cookies.txt"))

    @property
    def mode(self) -> str:
        return self.raw["course"].get("mode", "auto")

    @property
    def reference_otf(self) -> Path:
        return self.resolve(self.raw["font"]["reference_otf"])

    @property
    def cache_file(self) -> Path:
        return self.resolve(self.raw["font"].get("cache", ".cache/cand_matrix.npz"))

    @property
    def output_dir(self) -> Path:
        return self.resolve(self.raw.get("output", {}).get("dir", "out"))

    @property
    def browser(self) -> dict[str, Any]:
        return self.raw.get("browser", {})


def load_config(path: str | Path) -> Config:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p} (copy config.example.yaml to config.yaml)")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "course" not in data or "main_url" not in data["course"]:
        raise ValueError("config: missing course.main_url")
    return Config(path=p, raw=data)
