#!/usr/bin/env python3
from __future__ import annotations

import json
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
STATE = (WORKSPACE_ROOT / 'memory' / 'quiet-hours-enabled.json').resolve()


def main() -> int:
    if not STATE.exists():
        print('OK|조용시간 비활성(일반 운영 시간대)')
        return 0
    try:
        data = json.loads(STATE.read_text(encoding='utf-8'))
        n = len(data.get('jobIds') or [])
        captured = str(data.get('capturedAt', '-'))
        print(f'WARN|조용시간 활성(비활성 처리된 작업 {n}개, capturedAt={captured})')
    except Exception:
        age_h = int((time.time() - STATE.stat().st_mtime) // 3600)
        print(f'WARN|조용시간 상태파일 존재(파싱 실패, 마지막 수정 {age_h}h 전)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
