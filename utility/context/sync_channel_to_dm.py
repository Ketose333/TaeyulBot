#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re

ROOT = Path('/home/user/.openclaw/workspace')
CH_DIR = ROOT / 'memory/channels'
DM_PATH = CH_DIR / 'discord_dm_ketose.md'

SECTION = '## EXPORT_TO_DM'
ALLOWED = ('[RULE]', '[DECISION]', '[FAILURE]')


def extract_block(text: str, heading: str) -> list[str]:
    i = text.find(heading)
    if i < 0:
        return []
    tail = text[i + len(heading):]
    j = tail.find('\n## ')
    block = tail if j < 0 else tail[:j]
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if ln.startswith('- '):
            body = ln[2:].strip()
            if body.startswith(ALLOWED):
                lines.append(body)
    return lines


def build_import_section(items: list[tuple[str, str]]) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out = [
        '## IMPORT_FROM_CHANNELS',
        f'- last_sync: {now}',
        '- policy: [RULE]/[DECISION]/[FAILURE] 태그가 붙은 항목만 반영',
    ]
    if not items:
        out.append('- (none)')
    else:
        for src, line in items:
            out.append(f'- ({src}) {line}')
    return '\n'.join(out) + '\n'


def upsert_dm(section_text: str):
    text = DM_PATH.read_text(encoding='utf-8')
    h = '## IMPORT_FROM_CHANNELS'
    if h in text:
        pre, rest = text.split(h, 1)
        m = re.search(r'\n## ', rest)
        if m:
            text = pre + section_text + '\n' + rest[m.start()+1:]
        else:
            text = pre + section_text
    else:
        if not text.endswith('\n'):
            text += '\n'
        text += '\n' + section_text
    DM_PATH.write_text(text, encoding='utf-8')


def main():
    items = []
    for p in sorted(CH_DIR.glob('discord_*.md')):
        if p.name == 'discord_dm_ketose.md':
            continue
        lines = extract_block(p.read_text(encoding='utf-8'), SECTION)
        for line in lines:
            items.append((p.stem, line))
    sec = build_import_section(items)
    upsert_dm(sec)
    print(f'synced {len(items)} items from channel->dm')


if __name__ == '__main__':
    main()
