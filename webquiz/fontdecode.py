# -*- coding: utf-8 -*-
"""Decode Chaoxing's per-page ``font-cxsecret`` obfuscation.

The page embeds a TrueType subset as base64.  HTML code points are unrelated
CJK characters; the glyph outlines are the real characters.  The subset is
regenerated on every page load, so always decode the *current* page HTML.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

FONT_RE = re.compile(r"base64,([A-Za-z0-9+/=]{800,})")
SIZE = 56
GRID = 48


def extract_font_bytes(html: str) -> bytes | None:
    m = FONT_RE.search(html or "")
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1))
    except Exception:
        return None


def font_codepoints(ttf_bytes: bytes) -> list[int]:
    font = TTFont(io.BytesIO(ttf_bytes))
    return sorted(font.getBestCmap())


def _render_vector(font_source, ch: str):
    """Render one char and return a normalized 2304-dim vector."""
    try:
        if isinstance(font_source, (bytes, bytearray)):
            font_source = io.BytesIO(font_source)
        elif hasattr(font_source, "seek"):
            font_source.seek(0)
        # else: a path string / Path, use as-is
        font = ImageFont.truetype(font_source, SIZE)
    except Exception:
        return None
    im = Image.new("L", (SIZE * 2, SIZE * 2), 255)
    try:
        ImageDraw.Draw(im).text((SIZE // 2, SIZE // 2), ch, font=font, fill=0)
    except Exception:
        return None
    a = np.asarray(im)
    ys, xs = np.where(a < 200)
    if len(xs) == 0:
        return None
    im = im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    im = im.resize((GRID, GRID), Image.LANCZOS)
    v = 255.0 - np.asarray(im, dtype=np.float32)
    v -= v.mean()
    n = np.linalg.norm(v)
    return (v / n).ravel() if n else None


def build_reference_matrix(reference_otf: Path, cache_file: Path):
    """Cache a matrix of all reference-font chars. Returns (matrix, chars)."""
    if cache_file.exists():
        d = np.load(cache_file, allow_pickle=True)
        return d["M"], [str(x) for x in d["chars"]]

    cmap = TTFont(str(reference_otf)).getBestCmap()
    chars = [
        chr(cp)
        for cp in cmap
        if 0x20 <= cp <= 0x2FFF
        or 0x3000 <= cp <= 0x9FFF
        or 0xF900 <= cp <= 0xFAFF
        or 0xFF00 <= cp <= 0xFFEF
    ]
    vecs, kept = [], []
    for ch in chars:
        v = _render_vector(str(reference_otf), ch)
        if v is not None:
            vecs.append(v)
            kept.append(ch)
    if not vecs:
        raise RuntimeError(f"could not render reference font: {reference_otf}")
    M = np.stack(vecs)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_file, M=M, chars=np.array(kept))
    return M, kept


def decode_font(ttf_bytes: bytes, matrix, chars: list[str]):
    """Return {codepoint: (real_char, score)} for one embedded font."""
    mapping: dict[int, tuple[str, float]] = {}
    for cp in font_codepoints(ttf_bytes):
        v = _render_vector(ttf_bytes, chr(cp))
        if v is None:
            continue
        sims = matrix @ v
        j = int(np.argmax(sims))
        mapping[cp] = (chars[j], float(sims[j]))
    return mapping


def decode_html(html: str, reference_otf: Path, cache_file: Path):
    """Convenience: extract the first font from HTML and decode it."""
    ttf = extract_font_bytes(html)
    if not ttf:
        return {}
    M, chars = build_reference_matrix(reference_otf, cache_file)
    return decode_font(ttf, M, chars)


def decode_text(text: str, mapping: dict[int, tuple[str, float]]) -> str:
    return "".join(mapping.get(ord(c), (c, 0.0))[0] for c in text or "")
