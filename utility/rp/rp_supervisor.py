#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.memory_auto_log import append_daily
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    for _p in _Path(__file__).resolve().parents:
        if (_p / 'utility').exists():
            sys.path.append(str(_p))
            break
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.memory_auto_log import append_daily

WORKSPACE = Path('/home/user/.openclaw/workspace')
RUNTIME = WORKSPACE / 'utility/rp/discord_rp_runtime.py'
LOCK_PATH = WORKSPACE / 'memory/rp_rooms/_runtime_lock.json'
SUP_LOCK = WORKSPACE / 'memory/rp_rooms/_supervisor_lock.json'
ACTIVE_ROOMS = WORKSPACE / 'memory/rp_rooms/_active_rooms.json'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _write_supervisor_lock() -> None:
    SUP_LOCK.parent.mkdir(parents=True, exist_ok=True)
    SUP_LOCK.write_text(json.dumps({"pid": os.getpid(), "started_at": _utc_now()}, ensure_ascii=False, indent=2), encoding='utf-8')


def _check_singleton() -> bool:
    if not SUP_LOCK.exists():
        return True
    try:
        data = json.loads(SUP_LOCK.read_text(encoding='utf-8') or '{}')
        pid = int(data.get('pid') or 0)
        if _pid_alive(pid):
            print(f'supervisor already running: pid={pid}')
            return False
    except Exception:
        pass
    return True


def _recover_stale_runtime_lock() -> None:
    if not LOCK_PATH.exists():
        return
    try:
        data = json.loads(LOCK_PATH.read_text(encoding='utf-8') or '{}')
        pid = int(data.get('pid') or 0)
    except Exception:
        pid = 0
    if pid and _pid_alive(pid):
        return
    try:
        LOCK_PATH.unlink(missing_ok=True)
        print('recovered stale runtime lock')
        append_daily('- [RP 헬스] stale runtime lock 자동 복구')
    except Exception:
        pass


def _load_active_channel_ids() -> list[str]:
    if not ACTIVE_ROOMS.exists():
        return []
    try:
        obj = json.loads(ACTIVE_ROOMS.read_text(encoding='utf-8') or '{}')
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    ids: list[str] = []
    for _, meta in obj.items():
        if not isinstance(meta, dict):
            continue
        cid = str(meta.get('channel_id') or '').strip()
        if cid:
            ids.append(cid)
    # 순서 유지 중복 제거
    seen: set[str] = set()
    uniq: list[str] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        uniq.append(cid)
    return uniq


def _discord_bot_token() -> str:
    return (os.getenv('RP_DISCORD_BOT_TOKEN') or os.getenv('DISCORD_BOT_TOKEN') or '').strip()


def _discord_send_message(channel_id: str, content: str, token: str) -> bool:
    if not channel_id or not content or not token:
        return False
    url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
    body = json.dumps({'content': content}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={
            'Authorization': f'Bot {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'rp-supervisor/1.0',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            return True
    except urllib.error.HTTPError as e:
        print(f'discord notify failed({channel_id}): HTTP {e.code}')
        return False
    except Exception as e:
        print(f'discord notify failed({channel_id}): {e}')
        return False


def _notify_runtime_down(exit_code: int, lived_sec: float) -> int:
    token = _discord_bot_token()
    if not token:
        return 0
    channels = _load_active_channel_ids()
    if not channels:
        return 0

    msg = (
        f'⚠️ RP 런타임이 꺼졌어(code={exit_code}, up={lived_sec:.1f}s). 지금 자동 재시작 중이야. '
        f'안 붙으면 `!rp 시작`으로 다시 열어줘.'
    )
    ok = 0
    for cid in channels:
        if _discord_send_message(cid, msg, token):
            ok += 1
    return ok


def _term_handler(signum, frame):
    raise KeyboardInterrupt


def main() -> int:
    ap = argparse.ArgumentParser(description='RP runtime supervisor (auto-restart)')
    ap.add_argument('--min-restart-sec', type=float, default=1.0)
    ap.add_argument('--max-restart-sec', type=float, default=20.0)
    ap.add_argument('--stable-sec', type=float, default=120.0)
    args = ap.parse_args()

    if not _check_singleton():
        return 0

    load_env_prefer_dotenv()
    _write_supervisor_lock()

    signal.signal(signal.SIGTERM, _term_handler)
    signal.signal(signal.SIGINT, _term_handler)

    restart_wait = max(0.5, args.min_restart_sec)
    down_notified = False
    try:
        while True:
            _recover_stale_runtime_lock()
            started = time.time()
            proc = subprocess.Popen(['python3', str(RUNTIME)], cwd=str(WORKSPACE))
            code = proc.wait()
            lived = time.time() - started
            print(f'runtime exited code={code} lived={lived:.1f}s')

            if code in (0, 130):
                # intentional stop
                append_daily(f'- [RP 헬스] runtime 정상 종료(code={code}, lived={lived:.1f}s)')
                break

            append_daily(f'- [RP 헬스] runtime 비정상 종료(code={code}, lived={lived:.1f}s) -> 자동 재시작')

            if not down_notified:
                sent = _notify_runtime_down(exit_code=code, lived_sec=lived)
                if sent > 0:
                    append_daily(f'- [RP 헬스] 런타임 다운 알림 전송({sent}개 채널)')
                down_notified = True

            if lived >= args.stable_sec:
                restart_wait = max(0.5, args.min_restart_sec)
                down_notified = False
            else:
                restart_wait = min(args.max_restart_sec, max(args.min_restart_sec, restart_wait * 1.8))
            time.sleep(restart_wait)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            SUP_LOCK.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
