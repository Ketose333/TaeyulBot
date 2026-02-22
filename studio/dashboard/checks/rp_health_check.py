#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

LOCK = Path('/home/user/.openclaw/workspace/memory/rp_rooms/_runtime_lock.json')
ACTIVE = Path('/home/user/.openclaw/workspace/memory/rp_rooms/_active_rooms.json')


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _active_count() -> int:
    if not ACTIVE.exists():
        return 0
    try:
        data = json.loads(ACTIVE.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return len(data)
    except Exception:
        return 0
    return 0


def main() -> int:
    active_cnt = _active_count()
    if not LOCK.exists():
        if active_cnt > 0:
            print(f'WARN|RP 락 없음 · active_rooms {active_cnt} · recover 권장')
        else:
            print('OK|RP 미사용 또는 정상')
        return 0

    try:
        lock = json.loads(LOCK.read_text(encoding='utf-8'))
    except Exception:
        print('ERROR|RP 락 손상 · recover 필요')
        return 0

    pid = int(lock.get('pid') or 0)
    if _pid_alive(pid):
        print(f'OK|RP 정상 · active_rooms {active_cnt}')
    else:
        lv = 'ERROR' if active_cnt > 0 else 'WARN'
        print(f'{lv}|RP stale 락 · pid {pid} · active_rooms {active_cnt} · recover 권장')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
