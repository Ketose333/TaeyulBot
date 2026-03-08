#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from utility.common.generation_defaults import DEFAULT_IMAGE_ASPECT_RATIO, DEFAULT_IMAGE_MODEL

from utility.common.generation_defaults import WORKSPACE_ROOT

PRESETS_DIR = (WORKSPACE_ROOT / 'studio' / 'image' / 'presets').resolve()
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
    'model': DEFAULT_IMAGE_MODEL,
    'profile': 'ketose',
    'aspect_ratio': DEFAULT_IMAGE_ASPECT_RATIO,
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
