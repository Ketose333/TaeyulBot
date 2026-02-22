#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path('/home/user/.openclaw/workspace')


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description='Runtime audit for DM<->channel sync state')
    ap.add_argument('--apply', action='store_true', help='apply sync scripts before integrity check')
    args = ap.parse_args()

    steps: list[dict] = []

    if args.apply:
        for script in ['utility/context/sync_dm_rules.py', 'utility/context/sync_channel_to_dm.py']:
            code, out, err = run(['python3', script])
            steps.append({'step': script, 'ok': code == 0, 'stdout': out, 'stderr': err})
            if code != 0:
                print(json.dumps({'ok': False, 'failedAt': script, 'steps': steps}, ensure_ascii=False))
                return 1

    code, out, err = run(['python3', 'utility/context/check_sync_integrity.py'])
    integrity = None
    try:
        integrity = json.loads(out) if out else {'ok': False, 'problems': ['empty integrity output']}
    except Exception:
        integrity = {'ok': False, 'problems': ['invalid integrity json'], 'raw': out}

    dcode, diff_out, _ = run(['git', 'status', '--short', 'memory/channels/discord_dm_ketose.md', 'memory/global-context.md'])
    if dcode != 0:
        diff_out = ''

    result = {
        'ok': (code == 0) and bool(integrity.get('ok')),
        'applied': bool(args.apply),
        'integrity': integrity,
        'trackedChanges': [ln for ln in diff_out.splitlines() if ln.strip()],
        'steps': steps,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
