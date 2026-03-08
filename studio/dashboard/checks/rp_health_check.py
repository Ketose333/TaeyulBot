#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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
LOCK = (WORKSPACE_ROOT / 'memory' / 'rp_rooms' / '_runtime_lock.json').resolve()
ACTIVE = (WORKSPACE_ROOT / 'memory' / 'rp_rooms' / '_active_rooms.json').resolve()


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

    # OFF 상태는 경고가 아니라 정상으로 본다.
    if not LOCK.exists():
        print(f'OK|RP OFF · active_rooms {active_cnt}')
        return 0

    try:
        lock = json.loads(LOCK.read_text(encoding='utf-8'))
    except Exception:
        print('WARN|RP 락 손상 · recover 권장')
        return 0

    pid = int(lock.get('pid') or 0)
    if _pid_alive(pid):
        print(f'OK|RP 정상 · active_rooms {active_cnt}')
    else:
        print(f'WARN|RP stale 락 · pid {pid} · active_rooms {active_cnt} · recover 권장')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
