#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from utility.common.generation_defaults import WORKSPACE_ROOT
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    sys.path.append(str(_Path(__file__).resolve().parent.parent.parent.parent))
    from utility.common.bootstrap import ensure_utility_imports
    ensure_utility_imports(__file__)
    from utility.common.generation_defaults import WORKSPACE_ROOT
BASE = WORKSPACE_ROOT
RUNTIME_DIR = BASE / 'memory' / 'runtime'
QUEUE_PATH = RUNTIME_DIR / 'gitignore_hygiene_queue.jsonl'
RUNS_PATH = RUNTIME_DIR / 'gitignore_hygiene_runs.jsonl'
LOCK_PATH = RUNTIME_DIR / 'gitignore_hygiene_runtime.lock'
MAX_QUEUE_LINES = 200
MAX_RUNS_LINES = 50
MAX_FILES_IN_RUN = 200


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict[str, Any], *, max_lines: int | None = None) -> None:
    lines: list[str] = []
    if path.exists():
        try:
            lines = [ln for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip()]
        except Exception:
            lines = []
    lines.append(json.dumps(obj, ensure_ascii=False))
    if isinstance(max_lines, int) and max_lines > 0 and len(lines) > max_lines:
        lines = lines[-max_lines:]
    path.write_text(('\n'.join(lines) + ('\n' if lines else '')), encoding='utf-8')


def enqueue_job(*, reason: str = '') -> str:
    _ensure_dirs()
    job_id = f'ghyg-{int(time.time())}-{uuid.uuid4().hex[:8]}'
    job = {
        'id': job_id,
        'created_at': now_iso(),
        'reason': (reason or '').strip(),
        'status': 'queued',
    }
    _append_jsonl(QUEUE_PATH, job, max_lines=MAX_QUEUE_LINES)
    return job_id


def _pop_next_job() -> dict[str, Any] | None:
    _ensure_dirs()
    if not QUEUE_PATH.exists():
        return None
    lines = [ln for ln in QUEUE_PATH.read_text(encoding='utf-8').splitlines() if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    QUEUE_PATH.write_text(('\n'.join(lines[1:]) + ('\n' if len(lines) > 1 else '')), encoding='utf-8')
    return json.loads(first)


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    started = now_iso()
    # tracked + ignored files 목록 추출
    list_cmd = "git ls-files -ci --exclude-standard"
    p1 = subprocess.run(['bash', '-lc', list_cmd], cwd=str(BASE), capture_output=True, text=True)
    files = [ln.strip() for ln in (p1.stdout or '').splitlines() if ln.strip()]

    removed = 0
    rm_out = ''
    rm_err = ''
    code = 0
    if files:
        cmd = ['git', 'rm', '--cached', *files]
        p2 = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True)
        code = p2.returncode
        rm_out = (p2.stdout or '').strip()
        rm_err = (p2.stderr or '').strip()
        if code == 0:
            removed = len(files)

    finished = now_iso()
    status = 'ok' if code == 0 else 'error'
    return {
        'id': job.get('id'),
        'type': 'gitignore-hygiene',
        'started_at': started,
        'finished_at': finished,
        'status': status,
        'code': code,
        'job': job,
        'removed_count': removed,
        'tracked_ignored_count': len(files),
        'files': files[:MAX_FILES_IN_RUN],
        'stdout': rm_out,
        'stderr': rm_err,
    }


def _acquire_lock_or_exit() -> None:
    _ensure_dirs()
    if LOCK_PATH.exists():
        try:
            pid = int((LOCK_PATH.read_text(encoding='utf-8') or '0').strip() or '0')
            if pid > 0:
                os.kill(pid, 0)
                raise SystemExit(f'already running pid={pid}')
        except ProcessLookupError:
            pass
        except ValueError:
            pass
    LOCK_PATH.write_text(str(os.getpid()), encoding='utf-8')


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def runtime_loop(poll_sec: float = 10.0) -> int:
    _acquire_lock_or_exit()
    try:
        while True:
            job = _pop_next_job()
            if not job:
                time.sleep(max(1.0, poll_sec))
                continue
            result = _run_job(job)
            _append_jsonl(RUNS_PATH, result, max_lines=MAX_RUNS_LINES)
            print(f"[{result['finished_at']}] {result['id']} {result['status']} removed={result['removed_count']}")
    except KeyboardInterrupt:
        print('gitignore hygiene runtime stopped')
        return 130
    finally:
        _release_lock()


def main() -> int:
    ap = argparse.ArgumentParser(description='Gitignore hygiene runtime / enqueue helper')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_run = sub.add_parser('run')
    p_run.add_argument('--poll-sec', type=float, default=float(os.getenv('GITIGNORE_HYGIENE_RUNTIME_POLL_SEC', '10')))

    p_q = sub.add_parser('enqueue')
    p_q.add_argument('--reason', default='')

    args = ap.parse_args()
    if args.cmd == 'run':
        return runtime_loop(poll_sec=args.poll_sec)

    job_id = enqueue_job(reason=args.reason)
    print(json.dumps({'queued': True, 'job_id': job_id, 'queue': str(QUEUE_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
