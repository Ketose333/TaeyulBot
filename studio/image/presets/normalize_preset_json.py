#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PRESETS_DIR = Path('/home/user/.openclaw/workspace/studio/image/presets')
ORDER = [
    'name',
    'description',
    'model',
    'profile',
    'aspect_ratio',
    'count',
    'prompt',
    'output_name_pattern',
]
DEFAULTS = {
    'model': 'nano-banana-pro-preview',
    'profile': 'ketose',
    'aspect_ratio': '1:1',
    'count': 1,
}


def normalize_obj(src: dict) -> dict:
    out: dict = {}
    for k in ORDER:
        if k in src:
            out[k] = src[k]
        elif k in DEFAULTS:
            out[k] = DEFAULTS[k]

    for k, v in src.items():
        if k not in out:
            out[k] = v
    return out


def main() -> int:
    files = sorted(p for p in PRESETS_DIR.glob('*_preset.json') if p.is_file())
    for p in files:
        raw = json.loads(p.read_text(encoding='utf-8'))
        norm = normalize_obj(raw)
        p.write_text(json.dumps(norm, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'normalized: {p.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
