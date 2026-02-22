#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from pathlib import Path

CFG = Path('/home/user/.openclaw/workspace/studio/dashboard/config/sources.json')


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding='utf-8'))
    script = Path(cfg.get('dmSyncCheckScript', ''))
    if not script.exists():
        print('UNKNOWN|동기화 검사 스크립트가 없어.')
        return 0
    p = subprocess.run(['python3', str(script)], text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip().lower()
    if p.returncode == 0:
        print('OK|최근 점검에서 동기화 이상이 발견되지 않았어.')
        return 0
    if 'missing' in out or '누락' in out:
        print('ERROR|동기화 누락 항목이 있어. 상세 로그 확인이 필요해.')
    elif 'mismatch' in out or '불일치' in out:
        print('ERROR|동기화 불일치가 있어. 기준 소스 재동기화가 필요해.')
    else:
        print('ERROR|동기화 검사에서 오류가 발생했어. 검사 로그를 확인해줘.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
