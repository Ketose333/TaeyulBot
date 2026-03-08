#!/usr/bin/env python3
from __future__ import annotations

import json
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
ROOT = WORKSPACE_ROOT
DM = ROOT / 'memory/channels/discord_dm_ketose.md'
GLOBAL = ROOT / 'memory/global-context.md'

REQUIRED_DM_HEADINGS = [
    '## DM_CANONICAL_POLICY (authoritative)',
    '## IMPORT_FROM_CHANNELS',
    '## EXPORT_TO_ALL_CHANNELS',
]


def _has_nonempty_bullets(text: str, heading: str) -> bool:
    i = text.find(heading)
    if i < 0:
        return False
    tail = text[i + len(heading):]
    j = tail.find('\n## ')
    block = tail if j < 0 else tail[:j]
    lines = [ln.strip() for ln in block.splitlines() if ln.strip().startswith('- ')]
    if not lines:
        return False
    if len(lines) == 1 and lines[0] in {'- (empty)', '- (none)'}:
        return False
    return True


def main() -> int:
    ok = True
    problems: list[str] = []

    dm_text = DM.read_text(encoding='utf-8') if DM.exists() else ''
    global_text = GLOBAL.read_text(encoding='utf-8') if GLOBAL.exists() else ''

    if not DM.exists():
        ok = False
        problems.append('dm file missing')
    if not GLOBAL.exists():
        ok = False
        problems.append('global-context missing')

    for h in REQUIRED_DM_HEADINGS:
        if h not in dm_text:
            ok = False
            problems.append(f'missing heading: {h}')

    if not _has_nonempty_bullets(dm_text, '## DM_CANONICAL_POLICY (authoritative)'):
        ok = False
        problems.append('DM_CANONICAL_POLICY is empty')

    if '## DM_SYNC_EXPORT' not in global_text:
        ok = False
        problems.append('global DM_SYNC_EXPORT missing')

    if ok:
        print('OK|최근 점검에서 동기화 이상이 발견되지 않았어.')
    else:
        if any('missing' in p for p in problems):
            print('ERROR|동기화 누락 항목이 있어. 상세 로그 확인이 필요해.')
        else:
            print('ERROR|동기화 검사에서 오류가 발생했어. 검사 로그를 확인해줘.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
