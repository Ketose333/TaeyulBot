#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

WORKSPACE = Path('/home/user/.openclaw/workspace')
STATE_PATH = WORKSPACE / 'memory' / 'runtime' / 'studio_ui_runtime.json'

UI_TARGETS = {
    'cron': {
        'port': 8767,
        'cmd': ['python3', str(WORKSPACE / 'studio' / 'dashboard' / 'webui.py'), '--host', '0.0.0.0', '--port', '8767'],
    },
    'shorts': {
        'port': 8787,
        'cmd': ['python3', str(WORKSPACE / 'studio' / 'shorts' / 'webui.py'), '--host', '0.0.0.0', '--port', '8787'],
    },
    'image': {
        'port': 8791,
        'cmd': ['python3', str(WORKSPACE / 'studio' / 'image' / 'webui.py'), '--host', '0.0.0.0', '--port', '8791'],
    },
}


def _ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _ensure_state_dir()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _is_port_open(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        return s.connect_ex(('127.0.0.1', int(port))) == 0
    finally:
        s.close()


def _start_one(name: str, spec: dict, state: dict) -> str:
    prev = state.get(name, {})
    prev_pid = int(prev.get('pid', 0) or 0)
    if prev_pid and _is_pid_alive(prev_pid) and _is_port_open(spec['port']):
        return f'{name}: already running (pid={prev_pid}, port={spec["port"]})'

    proc = subprocess.Popen(spec['cmd'], cwd=str(WORKSPACE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state[name] = {'pid': proc.pid, 'port': spec['port'], 'startedAt': int(time.time())}
    return f'{name}: started pid={proc.pid} port={spec["port"]}'


def _stop_one(name: str, state: dict) -> str:
    info = state.get(name, {})
    pid = int(info.get('pid', 0) or 0)
    if not pid or not _is_pid_alive(pid):
        state.pop(name, None)
        return f'{name}: already stopped'
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    state.pop(name, None)
    return f'{name}: stopped pid={pid}'


def _status_one(name: str, spec: dict, state: dict) -> dict:
    info = state.get(name, {})
    pid = int(info.get('pid', 0) or 0)
    return {
        'name': name,
        'pid': pid if pid else None,
        'pidAlive': _is_pid_alive(pid) if pid else False,
        'port': spec['port'],
        'portOpen': _is_port_open(spec['port']),
    }


def _targets_from_arg(arg: str) -> list[str]:
    if arg == 'all':
        return list(UI_TARGETS.keys())
    if arg not in UI_TARGETS:
        raise SystemExit(f'unknown target: {arg}')
    return [arg]


def main() -> int:
    ap = argparse.ArgumentParser(description='Studio UI unified runtime controller')
    ap.add_argument('action', choices=['start', 'stop', 'restart', 'status'])
    ap.add_argument('--target', default='all', choices=['all', 'cron', 'shorts', 'image'])
    args = ap.parse_args()

    targets = _targets_from_arg(args.target)
    state = _load_state()

    if args.action == 'status':
        rows = [_status_one(t, UI_TARGETS[t], state) for t in targets]
        print(json.dumps({'ok': True, 'rows': rows}, ensure_ascii=False, indent=2))
        return 0

    logs: list[str] = []

    if args.action in {'stop', 'restart'}:
        for t in targets:
            logs.append(_stop_one(t, state))

    if args.action in {'start', 'restart'}:
        for t in targets:
            logs.append(_start_one(t, UI_TARGETS[t], state))

    _save_state(state)
    print('\n'.join(logs))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
