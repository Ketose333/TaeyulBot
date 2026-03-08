#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

try:
    from utility.common.generation_defaults import WORKSPACE_ROOT
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    sys.path.append(str(_Path(__file__).resolve().parent.parent.parent.parent))
    from utility.common.bootstrap import ensure_utility_imports
    ensure_utility_imports(__file__)
    from utility.common.generation_defaults import WORKSPACE_ROOT

THRESH = WORKSPACE_ROOT / 'studio/dashboard/config/thresholds.json'


def _extract_json(text: str) -> dict:
    i = text.find('{')
    if i < 0:
        return {}
    try:
        return json.loads(text[i:])
    except Exception:
        return {}


def _required_state_files_from_cron() -> list[Path]:
    cmd = [
        'openclaw', 'gateway', 'call', 'cron.list',
        '--timeout', '120000', '--params', '{"includeDisabled":true}'
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or '') + ('\n' + p.stderr if p.stderr else '')
    data = _extract_json(out)
    jobs = data.get('jobs', []) if isinstance(data, dict) else []

    target = None
    for j in jobs:
        if str(j.get('name', '')) == 'youtube-watch-uploads-10m':
            target = j
            break
    if not target:
        return []

    msg = str(((target.get('payload') or {}).get('message') or ''))
    ws = str(WORKSPACE_ROOT).replace('\\', '/')
    pat = rf"{re.escape(ws)}/memory/youtube-watch-[^\s`'\"]+\.json"
    paths = re.findall(pat, msg)
    return sorted({Path(p) for p in paths})


def main() -> int:
    files = _required_state_files_from_cron()
    if not files:
        print('UNKNOWN|youtube-watch-uploads-10m 설정에서 state 경로를 찾지 못했어.')
        return 0

    missing = [p for p in files if not p.exists()]
    if missing:
        print(f"ERROR|필수 state 누락 {len(missing)}개 ({missing[0].name} 등)")
        return 0

    now = time.time()
    ages = [int(now - p.stat().st_mtime) for p in files]
    max_age = max(ages)

    ok_min = 30
    warn_min = 120
    try:
        tcfg = json.loads(THRESH.read_text(encoding='utf-8'))
        y = tcfg.get('youtube', {})
        ok_min = int(y.get('okMaxMinutes', ok_min))
        warn_min = int(y.get('warnMaxMinutes', warn_min))
    except Exception:
        pass

    if max_age <= ok_min * 60:
        print(f"OK|필수 state {len(files)}개 최신(최대 {max_age//60}분 지연)")
    elif max_age <= warn_min * 60:
        print(f"WARN|필수 state {len(files)}개 일부 지연(최대 {max_age//60}분 지연)")
    else:
        print(f"ERROR|필수 state {len(files)}개 오래됨(최대 {max_age//3600}시간 지연)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
