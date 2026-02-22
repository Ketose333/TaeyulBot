#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

STATE = Path('/home/user/.openclaw/workspace/memory/quiet-hours-enabled.json')


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
