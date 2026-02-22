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

BASE = Path('/home/user/.openclaw/workspace')
RUNTIME_DIR = BASE / 'memory' / 'runtime'
QUEUE_PATH = RUNTIME_DIR / 'git_initial_reset_queue.jsonl'
RUNS_PATH = RUNTIME_DIR / 'git_initial_reset_runs.jsonl'
LOCK_PATH = RUNTIME_DIR / 'git_initial_reset_runtime.lock'
SCRIPT_PATH = BASE / 'utility' / 'git' / 'initial_reset_with_latest.sh'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def enqueue_job(*, apply_latest: bool = True, reason: str = '') -> tuple[str, bool]:
    _ensure_dirs()

    # 중복 방지: 동일 옵션 작업이 이미 큐에 있으면 재큐잉하지 않음
    queued = _load_jsonl(QUEUE_PATH)
    for q in queued:
        if bool(q.get('apply_latest', True)) == bool(apply_latest):
            return str(q.get('id') or ''), False

    # 중복 방지: 직전 성공 작업이 매우 최근이면 재큐잉하지 않음(기본 5분)
    cooldown_sec = int(os.getenv('GIT_INITIAL_RESET_ENQUEUE_COOLDOWN_SEC', '300'))
    runs = _load_jsonl(RUNS_PATH)
    if runs:
        last = runs[-1]
        if last.get('status') == 'ok' and bool((last.get('job') or {}).get('apply_latest', True)) == bool(apply_latest):
            try:
                ts = datetime.fromisoformat(str(last.get('finished_at') or ''))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age < cooldown_sec:
                    return str(last.get('id') or ''), False
            except Exception:
                pass

    job_id = f"ginit-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    job = {
        'id': job_id,
        'created_at': now_iso(),
        'apply_latest': bool(apply_latest),
        'reason': (reason or '').strip(),
        'status': 'queued',
    }
    _append_jsonl(QUEUE_PATH, job)
    return job_id, True


def _pop_next_job() -> dict[str, Any] | None:
    _ensure_dirs()
    if not QUEUE_PATH.exists():
        return None
    lines = QUEUE_PATH.read_text(encoding='utf-8').splitlines()
    jobs = [ln for ln in lines if ln.strip()]
    if not jobs:
        return None
    first = jobs[0]
    QUEUE_PATH.write_text(('\n'.join(jobs[1:]) + ('\n' if len(jobs) > 1 else '')), encoding='utf-8')
    return json.loads(first)


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    started = now_iso()
    cmd = ['bash', str(SCRIPT_PATH)]
    if not bool(job.get('apply_latest', True)):
        cmd.append('--no-latest')
    proc = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True)
    finished = now_iso()
    return {
        'id': job.get('id'),
        'type': 'git-initial-reset',
        'started_at': started,
        'finished_at': finished,
        'status': 'ok' if proc.returncode == 0 else 'error',
        'code': proc.returncode,
        'job': job,
        'stdout': (proc.stdout or '').strip(),
        'stderr': (proc.stderr or '').strip(),
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
        except PermissionError:
            raise SystemExit('lock exists and cannot verify owner')
    LOCK_PATH.write_text(str(os.getpid()), encoding='utf-8')


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def runtime_loop(poll_sec: float = 5.0) -> int:
    _acquire_lock_or_exit()
    try:
        while True:
            job = _pop_next_job()
            if not job:
                time.sleep(max(1.0, poll_sec))
                continue
            result = _run_job(job)
            _append_jsonl(RUNS_PATH, result)
            status = result['status']
            print(f"[{result['finished_at']}] {result['id']} {status} code={result['code']}")
    except KeyboardInterrupt:
        print('git initial-reset runtime stopped')
        return 130
    finally:
        _release_lock()


def main() -> int:
    ap = argparse.ArgumentParser(description='Git initial-reset runtime / enqueue helper')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_run = sub.add_parser('run')
    p_run.add_argument('--poll-sec', type=float, default=float(os.getenv('GIT_INITIAL_RESET_RUNTIME_POLL_SEC', '5')))

    p_q = sub.add_parser('enqueue')
    p_q.add_argument('--no-latest', action='store_true', help='queue reset without replaying latest patch')
    p_q.add_argument('--reason', default='')

    args = ap.parse_args()
    if args.cmd == 'run':
        return runtime_loop(poll_sec=args.poll_sec)

    job_id, queued = enqueue_job(apply_latest=not args.no_latest, reason=args.reason)
    print(json.dumps({'queued': queued, 'job_id': job_id, 'queue': str(QUEUE_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
