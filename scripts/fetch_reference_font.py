# -*- coding: utf-8 -*-
"""Download SourceHanSansSC-Normal.otf used as the glyph-matching reference."""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

URLS = [
    "https://ghfast.top/https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Normal.otf",
    "https://ghproxy.net/https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Normal.otf",
    "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Normal.otf",
]
OUT = Path(__file__).resolve().parent.parent / "assets" / "SourceHanSansSC-Normal.otf"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and OUT.stat().st_size > 1_000_000:
        print(f"already exists: {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")
        return
    last = None
    for url in URLS:
        try:
            print(f"downloading {url}")
            with urllib.request.urlopen(url, timeout=60) as r, open(OUT, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done/total*100:5.1f}%", end="", flush=True)
            print()
            if OUT.stat().st_size > 1_000_000:
                print(f"saved: {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")
                return
        except Exception as e:
            last = e
            print(f"  failed: {e}")
    sys.exit(f"could not download reference font: {last}")


if __name__ == "__main__":
    main()
