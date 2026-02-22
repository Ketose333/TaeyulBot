#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess


def _extract_json(text: str) -> dict:
    i = text.find('{')
    if i < 0:
        return {}
    try:
        return json.loads(text[i:])
    except Exception:
        return {}


def main() -> int:
    p = subprocess.run(['python3', '/home/user/.openclaw/workspace/studio/ui_runtime.py', 'status'], text=True, capture_output=True)
    out = (p.stdout or '') + ('\n' + p.stderr if p.stderr else '')
    data = _extract_json(out)
    rows = data.get('rows', []) if isinstance(data, dict) else []
    if not rows:
        print('ERROR|Studio UI 상태를 읽지 못했어')
        return 0

    down_pid = []
    down_port = []
    for r in rows:
        name = str(r.get('name', '-'))
        if not bool(r.get('pidAlive')):
            down_pid.append(name)
        if not bool(r.get('portOpen')):
            down_port.append(name)

    if not down_pid and not down_port:
        print(f'OK|Studio UI 정상({len(rows)}/{len(rows)})')
    else:
        msg = []
        if down_pid:
            msg.append('pid down: ' + ','.join(down_pid))
        if down_port:
            msg.append('port down: ' + ','.join(down_port))
        print('WARN|' + ' / '.join(msg))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
