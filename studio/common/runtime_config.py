from __future__ import annotations

import json
from pathlib import Path

from utility.common.path_roots import WORKSPACE_ROOT

NETWORK_CFG = WORKSPACE_ROOT / 'studio' / 'dashboard' / 'config' / 'network.json'

DEFAULT_UI_PORTS = {
    'cron': 8767,
    'shorts': 8787,
    'image': 8791,
    'music': 8795,
}


def load_network_cfg() -> dict:
    try:
        data = json.loads(NETWORK_CFG.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ui_ports() -> dict[str, int]:
    cfg = load_network_cfg()
    raw = cfg.get('ports') or []
    vals = []
    for x in raw:
        try:
            vals.append(int(x))
        except Exception:
            continue
    if len(vals) >= 4:
        return {
            'cron': vals[0],
            'shorts': vals[1],
            'image': vals[2],
            'music': vals[3],
        }
    return dict(DEFAULT_UI_PORTS)
