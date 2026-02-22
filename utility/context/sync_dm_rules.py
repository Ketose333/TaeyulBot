#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re

ROOT = Path('/home/user/.openclaw/workspace')
DM = ROOT / 'memory/channels/discord_dm_ketose.md'
GLOBAL = ROOT / 'memory/global-context.md'

START_CANDIDATES = ('## EXPORT_TO_ALL_CHANNELS', '## DM_CANONICAL_POLICY (authoritative)')


def extract_export_rules(text: str):
    i = -1
    for h in START_CANDIDATES:
        i = text.find(h)
        if i >= 0:
            i += len(h)
            break
    if i < 0:
        return []
    tail = text[i:]
    j = tail.find('\n## ')
    block = tail if j < 0 else tail[:j]
    rules = []
    for ln in block.splitlines():
        ln = ln.strip()
        if ln.startswith('- '):
            rules.append(ln)
    return rules


def upsert_global(rules):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    text = GLOBAL.read_text(encoding='utf-8') if GLOBAL.exists() else '# Global Context (shared, minimal)\n\n'

    section = '## DM_SYNC_EXPORT\n'
    body = '\n'.join(rules) + '\n' if rules else '- (empty)\n'
    stamp = f'- last_sync: {now}\n'
    new_block = f'{section}{stamp}{body}'

    if section in text:
        pre, rest = text.split(section, 1)
        # cut until next section
        m = re.search(r'\n## ', rest)
        if m:
            rest = rest[m.start()+1:]
            text = pre + new_block + '\n' + rest
        else:
            text = pre + new_block
    else:
        if not text.endswith('\n'):
            text += '\n'
        text += '\n' + new_block

    GLOBAL.write_text(text, encoding='utf-8')


def main():
    dm_text = DM.read_text(encoding='utf-8')
    rules = extract_export_rules(dm_text)
    upsert_global(rules)
    print(f'synced {len(rules)} rules')


if __name__ == '__main__':
    main()
