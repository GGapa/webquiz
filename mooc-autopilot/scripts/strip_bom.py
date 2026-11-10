# -*- coding: utf-8 -*-
"""去掉 .py 文件开头的 UTF-8 BOM（否则 ast.parse 会报 invalid non-printable character）。

用法：
    python scripts/strip_bom.py            # 处理 scripts/、mooc/、webquiz/
    python scripts/strip_bom.py 某个文件.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def strip(path: Path) -> bool:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        path.write_bytes(raw[3:])
        return True
    return False


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or list(REPO.rglob("*.py"))
    n = 0
    for p in targets:
        if p.is_file() and strip(p):
            print("去 BOM:", p.relative_to(REPO))
            n += 1
    print(f"共处理 {n} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
