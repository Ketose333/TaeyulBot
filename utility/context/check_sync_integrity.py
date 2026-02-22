#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/home/user/.openclaw/workspace')
DM = ROOT / 'memory/channels/discord_dm_ketose.md'
GLOBAL = ROOT / 'memory/global-context.md'

REQUIRED_DM_HEADINGS = [
    '## DM_CANONICAL_POLICY (authoritative)',
    '## IMPORT_FROM_CHANNELS',
    '## EXPORT_TO_ALL_CHANNELS',
]


def has_nonempty_bullets(text: str, heading: str) -> bool:
    i = text.find(heading)
    if i < 0:
        return False
    tail = text[i + len(heading):]
    j = tail.find('\n## ')
    block = tail if j < 0 else tail[:j]
    lines = [ln.strip() for ln in block.splitlines() if ln.strip().startswith('- ')]
    if not lines:
        return False
    # treat explicit empty marker as empty
    if len(lines) == 1 and lines[0] in {'- (empty)', '- (none)'}:
        return False
    return True


def main() -> int:
    ok = True
    problems: list[str] = []

    if not DM.exists():
        ok = False
        problems.append('dm file missing')
        dm_text = ''
    else:
        dm_text = DM.read_text(encoding='utf-8')

    if not GLOBAL.exists():
        ok = False
        problems.append('global-context missing')
        global_text = ''
    else:
        global_text = GLOBAL.read_text(encoding='utf-8')

    for h in REQUIRED_DM_HEADINGS:
        if h not in dm_text:
            ok = False
            problems.append(f'missing heading: {h}')

    if not has_nonempty_bullets(dm_text, '## DM_CANONICAL_POLICY (authoritative)'):
        ok = False
        problems.append('DM_CANONICAL_POLICY is empty')

    if '## DM_SYNC_EXPORT' not in global_text:
        ok = False
        problems.append('global DM_SYNC_EXPORT missing')

    out = {
        'ok': ok,
        'problems': problems,
        'dm': str(DM),
        'global': str(GLOBAL),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
