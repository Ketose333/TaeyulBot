from __future__ import annotations

import re
from pathlib import Path


def slugify_name(text: str, fallback: str = 'file') -> str:
    t = (text or '').lower().strip()
    t = re.sub(r'[^a-z0-9가-힣]+', '_', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t or fallback


def resolve_unique_name(out_dir: Path, name: str) -> str:
    p = Path(name)
    stem, suf = p.stem, p.suffix
    cand = out_dir / f"{stem}{suf}"
    i = 2
    while cand.exists():
        cand = out_dir / f"{stem}_{i}{suf}"
        i += 1
    return cand.name


def resolve_unique_path(out_dir: Path, stem_text: str, ext: str, fallback: str = 'file') -> Path:
    stem = slugify_name(stem_text, fallback=fallback)[:60]
    cand = out_dir / f"{stem}{ext}"
    i = 2
    while cand.exists():
        cand = out_dir / f"{stem}_{i}{ext}"
        i += 1
    return cand


def append_indexed_name(name: str, idx: int, count: int) -> str:
    if count <= 1:
        return name
    p = Path(name)
    return f"{p.stem}_{idx:02d}{p.suffix}"
