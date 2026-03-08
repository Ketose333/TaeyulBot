#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from http_handler import create_handler
from post_actions import handle_post
from view_context import build_dashboard_context

try:
    from utility.common.generation_defaults import WORKSPACE_ROOT
    from studio.common.runtime_config import ui_ports
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    sys.path.append(str(_Path(__file__).resolve().parent.parent))
    from common.bootstrap import ensure_workspace_imports
    ensure_workspace_imports(__file__)
    from utility.common.generation_defaults import WORKSPACE_ROOT
    from studio.common.runtime_config import ui_ports


def _val(form: dict[str, list[str]], key: str, default: str = "") -> str:
    return (form.get(key, [default])[0] or default).strip()


def _extract_json(text: str) -> dict:
    i = text.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(text[i:])
    except Exception:
        return {}


def _fmt_kst(ms: int | None) -> str:
    if ms is None:
        return '-'
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
        return dt.strftime('%m-%d %H:%M')
    except Exception:
        return str(ms)


def _due_label(ms: int | None, now_ms: int) -> str:
    if ms is None:
        return '-'
    d = int((ms - now_ms) / 1000)
    if d <= 0:
        return '지금/지연'
    m = d // 60
    if m < 1:
        return f'{d}s'
    if m < 60:
        return f'{m}m'
    h = m // 60
    if h < 24:
        return f'{h}h {m%60}m'
    return f'{h//24}d {h%24}h'


def gateway_call(method: str, params: dict) -> tuple[bool, dict, str]:
    cmd = [
        "openclaw",
        "gateway",
        "call",
        method,
        "--timeout",
        "150000",
        "--params",
        json.dumps(params, ensure_ascii=False),
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    data = _extract_json(out)
    return (p.returncode == 0), data, out[-1500:]


def studio_ui_status() -> tuple[bool, list[dict], str]:
    cmd = [PYTHON_BIN, str((WORKSPACE / 'studio' / 'ui_runtime.py').resolve()), "status"]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    data = _extract_json(out)
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return (p.returncode == 0), rows, out[-1200:]


WORKSPACE = WORKSPACE_ROOT
PYTHON_BIN = str((WORKSPACE / '.venv' / 'bin' / 'python')) if (WORKSPACE / '.venv' / 'bin' / 'python').exists() else 'python3'
CRON_FOCUS_RULES = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'cron_focus_rules.json'
DASHBOARD_CHECKS = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'dashboard_checks.json'
UI_TEXTS = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'ui_texts.json'
CRON_MANAGER_COLUMNS = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'cron_manager_columns.json'
SOURCES_CFG = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'sources.json'
DM_RUNTIME_DIR = WORKSPACE / 'studio' / 'dashboard' / 'runtime'
DM_BULK_LOCK = DM_RUNTIME_DIR / 'discord_bulk_delete_runtime.lock'
DM_QUEUE_PATH = DM_RUNTIME_DIR / 'discord_bulk_delete_queue.jsonl'
DM_RUNS_PATH = DM_RUNTIME_DIR / 'discord_bulk_delete_runs.jsonl'
PIN_MESSAGE_FILE = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'pinned_message.md'
PIN_MESSAGE_ACTION = WORKSPACE / 'studio' / 'dashboard' / 'actions' / 'discord_pin_message_action.py'
RP_RT_LOCK = WORKSPACE / 'memory' / 'rp_rooms' / '_runtime_lock.json'
RP_RUNTIME_SCRIPT = WORKSPACE / 'studio' / 'dashboard' / 'actions' / 'rp_runtime_action.py'
NETWORK_CFG = WORKSPACE / 'studio' / 'dashboard' / 'config' / 'network.json'


def _system_dup_signal(jobs: list[dict]) -> tuple[str, str]:
    target = None
    for j in jobs:
        if str(j.get('name', '')) == 'daily-ops-checkin-1200':
            target = j
            break
    if not target:
        return 'UNKNOWN', 'daily-ops-checkin-1200 미등록'
    st = target.get('state', {}) or {}
    last_status = str(st.get('lastStatus', '-'))
    if last_status.lower() in {'ok', '-'}:
        return 'OK', f'lastStatus={last_status}'
    return 'WARN', f'lastStatus={last_status}'




def _aiven_mysql_status() -> tuple[str, str, str]:
    cmd = [PYTHON_BIN, str((WORKSPACE / 'studio' / 'dashboard' / 'checks' / 'aiven_service_check.py').resolve()), 'mysql-budget']
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    data = _extract_json(out)
    state = str((data.get('state') if isinstance(data, dict) else '') or '').upper()
    if state in {'RUNNING', 'REBALANCING'}:
        return 'RUN', '#22c55e', state
    if state:
        return 'ISSUE', '#ef4444', state
    return 'WARN', '#f59e0b', (out.splitlines()[-1] if out else 'unknown')[:40]


def _resolve_cfg_path(raw: str, cfg_file: Path) -> str:
    s = str(raw or '').strip()
    if not s:
        return s
    p = Path(s).expanduser()
    if p.is_absolute():
        return str(p.resolve())
    return str((cfg_file.parent / p).resolve())


def _load_dashboard_checks() -> list[dict]:
    try:
        data = json.loads(DASHBOARD_CHECKS.read_text(encoding='utf-8'))
        if isinstance(data, list):
            out = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                item = dict(row)
                if item.get('type') == 'script' and item.get('script'):
                    item['script'] = _resolve_cfg_path(str(item.get('script')), DASHBOARD_CHECKS)
                out.append(item)
            return out
    except Exception:
        pass
    return []



def _load_ui_texts() -> dict:
    try:
        return json.loads(UI_TEXTS.read_text(encoding='utf-8'))
    except Exception:
        return {
            'appTitle':'Studio Dashboard',
            'tabDashboard':'대시보드',
            'tabCronManager':'크론 매니저',
            'sections':{},'buttons':{}
        }




def _load_sources_cfg() -> dict:
    try:
        data = json.loads(SOURCES_CFG.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        out = dict(data)
        globs = out.get('youtubeStateGlobs') or []
        if isinstance(globs, list):
            out['youtubeStateGlobs'] = [_resolve_cfg_path(str(x), SOURCES_CFG) for x in globs]
        return out
    except Exception:
        return {}


def _load_cron_columns() -> list[dict]:
    try:
        data=json.loads(CRON_MANAGER_COLUMNS.read_text(encoding='utf-8'))
        cols=[c for c in (data.get('columns') or []) if c.get('enabled',True)]
        return cols
    except Exception:
        return [
            {'key':'name','label':'이름','enabled':True},
            {'key':'enabled','label':'enabled','enabled':True},
            {'key':'schedule','label':'schedule','enabled':True},
            {'key':'nextRun','label':'nextRunAtMs','enabled':True},
            {'key':'actions','label':'액션','enabled':True},
        ]


def _run_script_check(script: str) -> tuple[str, str]:
    p = subprocess.run([PYTHON_BIN, script], text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if '|' in out:
        lv, msg = out.split('|', 1)
        return lv.strip(), msg.strip()
    return 'UNKNOWN', (out or '체크 결과를 읽지 못했어.')[:140]


def _rp_status() -> tuple[bool, str]:
    try:
        if not RP_RT_LOCK.exists():
            return False, 'OFF'
        obj = json.loads(RP_RT_LOCK.read_text(encoding='utf-8') or '{}')
        pid = int(obj.get('pid') or 0)
        if pid <= 1:
            return False, 'OFF'
        cmdline = Path(f'/proc/{pid}/cmdline').read_text(errors='ignore')
        if 'rp_runtime_action.py' in cmdline:
            return True, 'ON (runtime=on)'
        return False, 'OFF'
    except Exception:
        return False, 'OFF'


def _rp_recover_only() -> tuple[bool, str]:
    cmd = [PYTHON_BIN, str((WORKSPACE / 'utility' / 'taeyul' / 'taeyul_cli.py').resolve()), 'rp-healthcheck', '--recover']
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()

    msg = 'RP 복구 점검 완료'
    try:
        obj = json.loads(p.stdout or '{}') if (p.stdout or '').strip() else {}
        if isinstance(obj, dict):
            issues = obj.get('issues') or []
            recovered = obj.get('recovered') or []
            if recovered:
                msg = f'RP 복구 완료 ({len(recovered)}건 정리)'
            elif issues:
                msg = f'RP 점검 완료 (이슈 {len(issues)}건 남음)'
            else:
                msg = 'RP 점검 완료'
    except Exception:
        if out:
            last = out.splitlines()[-1].strip()
            if last and last != '}':
                msg = last[:160]

    if p.returncode == 0:
        return True, msg
    return False, msg if msg else 'RP 복구 실패'


def _rp_turn_on() -> tuple[bool, str]:
    on, st = _rp_status()
    if on:
        ok, msg = _rp_recover_only()
        return ok, f'RP 이미 ON · {msg}'

    ok, rec = _rp_recover_only()
    cmd = [PYTHON_BIN, str(RP_RUNTIME_SCRIPT)]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    on2, st2 = _rp_status()
    if on2:
        return True, f'RP ON 완료 · {st2} · {rec}'
    return False, f'RP ON 실패 · {rec}'


def _rp_turn_off() -> tuple[bool, str]:
    killed = 0
    try:
        if RP_RT_LOCK.exists():
            obj = json.loads(RP_RT_LOCK.read_text(encoding='utf-8') or '{}')
            pid = int(obj.get('pid') or 0)
            if pid > 1:
                try:
                    os.kill(pid, 15)
                    killed += 1
                except Exception:
                    pass
            RP_RT_LOCK.unlink(missing_ok=True)
    except Exception:
        pass

    try:
        subprocess.run(['pkill', '-f', 'rp_runtime_action.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    time.sleep(0.5)
    on, st = _rp_status()
    if not on:
        return True, f'RP OFF 완료 (정리 {killed}개)'
    return False, f'RP OFF 일부 실패 · {st}'

def _ensure_dm_bulk_runtime() -> None:
    # stale lock 정리
    try:
        if DM_BULK_LOCK.exists():
            pid_txt = (DM_BULK_LOCK.read_text(encoding='utf-8') or '').strip()
            pid = int(pid_txt or '0') if pid_txt.isdigit() else 0
            remove_lock = False
            if pid <= 1:
                remove_lock = True
            else:
                cmdline = ''
                try:
                    cmdline = Path(f'/proc/{pid}/cmdline').read_text(errors='ignore')
                except Exception:
                    remove_lock = True
                if cmdline and 'discord_bulk_delete_action.py' not in cmdline:
                    remove_lock = True
            if remove_lock:
                DM_BULK_LOCK.unlink(missing_ok=True)
    except Exception:
        pass

    cmd = [
        PYTHON_BIN,
        str((WORKSPACE / 'studio' / 'dashboard' / 'actions' / 'discord_bulk_delete_action.py').resolve()),
        'run', '--poll-sec', '2'
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _dm_bulk_delete_enqueue(channel_id: str, limit: int, delete_pinned: bool = False) -> tuple[bool, str]:
    script = str((WORKSPACE / 'studio' / 'dashboard' / 'actions' / 'discord_bulk_delete_action.py').resolve())
    cmd = [
        PYTHON_BIN, script,
        'enqueue', '--channel-id', channel_id, '--limit', str(limit),
        '--auto-author', '--no-skip-pinned' if delete_pinned else '--skip-pinned'
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        _ensure_dm_bulk_runtime()
        return True, (out.splitlines()[-1] if out else 'DM 일괄 삭제 큐 등록 완료')
    return False, (out.splitlines()[-1] if out else 'DM 일괄 삭제 큐 등록 실패')


def _create_and_pin_message(channel_id: str) -> tuple[bool, str]:
    if not PIN_MESSAGE_FILE.exists():
        return False, f'파일 없음: {PIN_MESSAGE_FILE}'
    cmd = [
        PYTHON_BIN, str(PIN_MESSAGE_ACTION),
        '--channel-id', str(channel_id),
        '--text-path', str(PIN_MESSAGE_FILE),
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        return True, (out.splitlines()[-1] if out else '고정 메시지 생성/고정 완료')
    return False, (out.splitlines()[-1] if out else '고정 메시지 생성/고정 실패')


def _commit_push(message: str, target: str = 'workspace') -> tuple[bool, str]:
    default_msg = 'chore(tcg): update from dashboard' if target == 'tcg' else 'chore(workspace): update from dashboard'
    msg = (message or '').strip() or default_msg
    repo_dir = str((WORKSPACE / 'tcg').resolve()) if target == 'tcg' else str(WORKSPACE.resolve())
    cmd = [
        'bash', '-lc',
        (
            f"cd {json.dumps(repo_dir)} && git add -A && "
            "CURRENT_BRANCH=\"$(git rev-parse --abbrev-ref HEAD)\" && "
            "if git diff --cached --quiet; then "
            "  if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then "
            "    if [ -n \"$(git log --oneline @{u}..HEAD)\" ]; then "
            "      (git push || git push --set-upstream origin \"$CURRENT_BRANCH\") && echo 'PUSHED_AHEAD'; "
            "    else "
            "      echo 'NO_CHANGES'; "
            "    fi; "
            "  else "
            "    if [ -n \"$(git log --oneline)\" ]; then "
            "      (git push --set-upstream origin \"$CURRENT_BRANCH\" || git push) && echo 'PUSHED_AHEAD'; "
            "    else "
            "      echo 'NO_CHANGES'; "
            "    fi; "
            "  fi; "
            "else "
            f"  git commit -m {json.dumps(msg)} && (git push --set-upstream origin \"$CURRENT_BRANCH\" || git push); "
            "fi"
        )
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if 'PUSHED_AHEAD' in out:
        return True, f'[{target}] 로컬 커밋(앞선 이력) 푸시 완료.'
    if 'NO_CHANGES' in out:
        return True, f'[{target}] 커밋할 변경사항이 없어.'
    if p.returncode == 0:
        tail = out.splitlines()[-1] if out else '커밋/푸시 완료'
        return True, f'[{target}] {tail}'
    tail = out.splitlines()[-1] if out else '커밋/푸시 실패'
    return False, f'[{target}] {tail}'


def _initial_reset_run(reason: str, target: str = 'workspace') -> tuple[bool, str]:
    repo_dir = str((WORKSPACE / 'tcg').resolve()) if target == 'tcg' else str(WORKSPACE.resolve())
    reason_clean = ' '.join((reason or '').split()).strip()
    if reason_clean:
        init_msg = f'chore: initial commit ({reason_clean})'
    else:
        init_msg = 'chore: initial commit'

    # 커밋+푸시와 동일하게 대시보드 내부에서 직접 실행(외부 스크립트 의존 제거)
    cmd = [
        'bash', '-lc',
        (
            f"set -euo pipefail; cd {json.dumps(repo_dir)}; "
            "CURRENT_BRANCH=\"$(git rev-parse --abbrev-ref HEAD)\"; "
            "git checkout --orphan temp_initial_dashboard; "
            "git add -A; "
            f"git commit -m {json.dumps(init_msg)}; "
            "git branch -D \"$CURRENT_BRANCH\"; "
            "git branch -m \"$CURRENT_BRANCH\"; "
            "git push --force-with-lease origin \"$CURRENT_BRANCH\"; "
            "echo done: dashboard initial reset completed"
        )
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        tail = out.splitlines()[-1] if out else '이니셜 커밋 밀기 완료'
        return True, f'[{target}] {tail}'
    tail = out.splitlines()[-1] if out else '이니셜 커밋 밀기 실패'
    return False, f'[{target}] {tail}'




def _load_network_cfg() -> dict:
    try:
        return json.loads(NETWORK_CFG.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _remote_urls() -> list[str]:
    cfg = _load_network_cfg()
    ip = str(cfg.get('lanHostIp', '') or '').strip()
    host = str(cfg.get('hostName', '') or '').strip()
    ports = list(ui_ports().values())
    out = []
    for p in ports:
        try:
            pp = int(p)
        except Exception:
            continue
        if ip:
            out.append(f'http://{ip}:{pp}')
        if host:
            out.append(f'http://{host}:{pp}')
    # dedupe keep order
    seen=set(); uniq=[]
    for u in out:
        if u in seen: continue
        seen.add(u); uniq.append(u)
    return uniq


def _run_portproxy_update() -> tuple[bool, str]:
    cfg = _load_network_cfg()
    script = str(cfg.get('portproxyScriptWindows', '') or '').strip()
    ports = list(ui_ports().values())
    ports_arg = ','.join(str(int(x)) for x in ports if str(x).isdigit()) or ','.join(str(x) for x in ui_ports().values())
    if not script:
        return False, 'network.json에 portproxyScriptWindows가 없어.'

    cmds = [
        ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', script, '-Ports', ports_arg],
        ['pwsh', '-ExecutionPolicy', 'Bypass', '-File', script, '-Ports', ports_arg],
    ]
    last = ''
    for cmd in cmds:
        try:
            p = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
            out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
            if p.returncode == 0:
                return True, (out.splitlines()[-1] if out else 'portproxy 갱신 완료')
            last = out[-260:]
        except Exception as e:
            last = str(e)
    manual = (
        "자동 실행 실패. 아래 관리자 PowerShell 한 줄을 그대로 실행해줘:\n"
        f"Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -Command \"$src=''\\\\wsl.localhost\\Ubuntu\\home\\user\\.openclaw\\workspace\\utility\\common\\windows_wsl_portproxy_autoupdate.ps1''; $dst=Join-Path $env:TEMP ''windows_wsl_portproxy_autoupdate.ps1''; if(!(Test-Path $src)){{throw ''스크립트 없음''}}; Copy-Item $src $dst -Force; Unblock-File $dst; Set-ExecutionPolicy -Scope Process Bypass -Force; & $dst -Ports ''{ports_arg}''\"'"
    )
    return False, manual


def _start_all_studio_uis() -> tuple[bool, str]:
    cmd = ['python3', str((WORKSPACE / 'studio' / 'ui_runtime.py').resolve()), 'start', '--target', 'all']
    try:
        p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, timeout=60)
    except Exception as e:
        return False, f'UI 일괄 실행 실패: {e}'

    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode != 0:
        tail = out.splitlines()[-1] if out else 'UI 일괄 실행 실패'
        return False, tail

    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    started = sum('started pid=' in ln for ln in lines)
    already = sum('already running' in ln for ln in lines)
    return True, f'UI 일괄 실행 완료: 새로 켠 {started}개 · 이미 실행 중 {already}개'


def _cleanup_vercel_deployments(dry_run: bool = False) -> tuple[bool, str]:
    tcg_dir = WORKSPACE / 'tcg'
    project_name = 'nulsight'
    scope = 'team_QtyiuCIFBns7dbiuGkXiPKgq'

    list_cmd = ['vercel', 'list', project_name, '--yes', '--scope', scope]
    lp = subprocess.run(list_cmd, cwd=str(tcg_dir), text=True, capture_output=True)
    lout = ((lp.stdout or '') + ('\n' + lp.stderr if lp.stderr else '')).strip()
    if lp.returncode != 0:
        tail = lout.splitlines()[-1] if lout else '배포 목록 조회 실패'
        return False, tail

    urls = []
    for ln in lout.splitlines():
        s = ln.strip()
        if s.startswith('https://') and '.vercel.app' in s:
            urls.append(s)

    if len(urls) <= 1:
        return True, '정리할 이전 배포가 없어.'

    keep = urls[0]
    targets = urls[1:]

    if dry_run:
        return True, f'dry-run: keep 1개, delete 대상 {len(targets)}개'

    deleted = 0
    for u in targets:
        dp = subprocess.run(['vercel', 'remove', u, '--yes', '--scope', scope], cwd=str(tcg_dir), text=True, capture_output=True)
        if dp.returncode == 0:
            deleted += 1

    if deleted == len(targets):
        return True, f'배포 정리 완료: keep 1개 ({keep}), 삭제 {deleted}개'
    return False, f'배포 정리 부분 실패: keep 1개 ({keep}), 삭제 {deleted}/{len(targets)}개'


def _dm_bulk_runtime_status() -> tuple[str, str, str]:
    alive = False
    pid = None
    try:
        if DM_BULK_LOCK.exists():
            pid_txt = (DM_BULK_LOCK.read_text(encoding='utf-8') or '').strip()
            if pid_txt.isdigit():
                pid = int(pid_txt)
                cmdline = Path(f'/proc/{pid}/cmdline').read_text(errors='ignore')
                alive = 'discord_bulk_delete_action.py' in cmdline
    except Exception:
        alive = False

    qn = 0
    try:
        if DM_QUEUE_PATH.exists():
            qn = len([ln for ln in DM_QUEUE_PATH.read_text(encoding='utf-8').splitlines() if ln.strip()])
    except Exception:
        qn = 0

    last = '-'
    try:
        if DM_RUNS_PATH.exists():
            lines = [ln for ln in DM_RUNS_PATH.read_text(encoding='utf-8').splitlines() if ln.strip()]
            if lines:
                obj = json.loads(lines[-1])
                st = str(obj.get('status', '-')).upper()
                out = str(obj.get('stdout', '') or '')
                tail = (out.splitlines()[-1] if out else '')[:48]
                last = f"{st} · {tail}" if tail else st
    except Exception:
        pass

    if alive:
        return 'RUN', '#22c55e', f'queue {qn} · {last}'
    return 'DOWN', '#ef4444', f'queue {qn} · {last}'


def render_page(alert: str = "") -> bytes:
    ctx = build_dashboard_context(alert, {
        "gateway_call": gateway_call,
        "load_ui_texts": _load_ui_texts,
        "load_sources_cfg": _load_sources_cfg,
        "dm_bulk_runtime_status": _dm_bulk_runtime_status,
        "rp_status": _rp_status,
        "studio_ui_status": studio_ui_status,
        "aiven_mysql_status": _aiven_mysql_status,
        "load_network_cfg": _load_network_cfg,
        "ui_ports": ui_ports,
        "load_dashboard_checks": _load_dashboard_checks,
        "run_script_check": _run_script_check,
        "system_dup_signal": _system_dup_signal,
        "load_cron_columns": _load_cron_columns,
        "fmt_kst": _fmt_kst,
        "due_label": _due_label,
    })

    jobs = ctx["jobs"]
    ui_txt = ctx["ui_txt"]
    sec = ctx["sec"]
    dm_channel_id = ctx["dm_channel_id"]
    dm_rt_label = ctx["dm_rt_label"]
    dm_rt_color = ctx["dm_rt_color"]
    dm_rt_detail = ctx["dm_rt_detail"]
    rp_on = ctx["rp_on"]
    rp_state_text = ctx["rp_state_text"]
    rows = ctx["rows"]
    enabled_count = ctx["enabled_count"]
    disabled_count = ctx["disabled_count"]
    problem_count = ctx["problem_count"]
    issue_rows = ctx["issue_rows"]
    ui_running = ctx["ui_running"]
    ui_rows = ctx["ui_rows"]
    ui_cards = ctx["ui_cards"]
    ui_err_html = ctx["ui_err_html"]
    app_cards_html = ctx["app_cards_html"]
    remote_urls_html = ctx["remote_urls_html"]
    dashboard_check_rows = ctx["dashboard_check_rows"]
    cron_head_html = ctx["cron_head_html"]
    alert_html = ctx["alert_html"]
    err_html = ctx["err_html"]

    body = f"""
<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{html.escape(ui_txt.get('appTitle','Studio Dashboard'))}</title>
<style>
html,body{{max-width:100%;overflow-x:hidden}}
body{{font-family:system-ui,sans-serif;background:#0f1520;color:#e9eef5;margin:0;padding:16px}}
.wrap{{max-width:1280px;margin:0 auto;min-width:0}}
.panel{{background:#182131;border:1px solid #2b3a52;border-radius:12px;padding:14px;margin-bottom:12px;min-width:0}}
h1,h2{{margin:0 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;min-width:0}}
.full{{grid-column:1/-1}}
input,select,textarea,button{{width:100%;box-sizing:border-box;background:#0f1725;color:#e9eef5;border:1px solid #344862;border-radius:8px;padding:8px}}
input::placeholder,textarea::placeholder{{color:#9fb0cb}}
.muted,.op-desc,.op-title,.tl-name,a,th,td{{overflow-wrap:anywhere;word-break:break-word}}
button{{cursor:pointer}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{border:1px solid #30435f;padding:7px;vertical-align:top}}
.alert{{background:#143321;border:1px solid #2aa748;padding:10px;border-radius:8px;margin-bottom:12px}}
.err{{white-space:pre-wrap;background:#2a1616;padding:10px;border-radius:8px}}
.badge{{display:inline-block;background:#4a1d1d;border:1px solid #8e3b3b;color:#ffd9d9;border-radius:999px;padding:2px 8px;font-size:12px;margin:2px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}}
.stat{{background:#0f1725;border:1px solid #30435f;border-radius:10px;padding:10px}}
.stat .k{{font-size:11px;color:#a9b7cf}}
.stat .v{{font-size:18px;font-weight:700}}
.tl-row{{display:grid;grid-template-columns:180px 1fr 78px;gap:8px;align-items:center;margin:6px 0}}
.tl-name{{font-size:12px;color:#d7e2f2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tl-bar-wrap{{height:8px;background:#0b1220;border:1px solid #2a3a54;border-radius:999px;overflow:hidden}}
.tl-bar{{height:100%}}
.tl-when{{font-size:11px;color:#a9b7cf;text-align:right}}
.muted{{color:#9fb0cb;font-size:12px}}
.tabs{{position:sticky;top:0;z-index:10;display:flex;gap:8px;margin:0 0 10px;padding:8px;background:rgba(15,21,32,.88);backdrop-filter:blur(4px)}}
.tab-btn{{width:auto;padding:7px 11px}}
.tab-btn.active{{background:#1f3a63;border-color:#4c79b6}}
.tab-panel{{display:none}}
.tab-panel.active{{display:block}}
.dash-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.col-span-2{{grid-column:1/-1}}
details.fold > summary{{cursor:pointer;font-weight:700;list-style:none;margin:-2px 0 8px 0}}
details.fold > summary::-webkit-details-marker{{display:none}}
.op-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.op-card{{background:#0f1725;border:1px solid #30435f;border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px}}
.op-card.danger{{border-color:#6b2a2a;background:#1b1318}}
.op-title{{font-size:14px;font-weight:700}}
.op-desc{{font-size:12px;color:#a9b7cf}}
.op-label{{font-size:12px;color:#9fb0cb}}
.op-check{{font-size:12px;color:#d7e2f2;display:flex;gap:8px;align-items:center}}
.btn{{width:100%;min-height:44px;padding:10px;border-radius:10px;font-weight:700}}
.btn-green{{background:#173b2a;border:1px solid #2aa748;color:#e9eef5}}
.btn-lime{{background:#2f3f17;border:1px solid #9acb47;color:#e9eef5}}
.btn-blue{{background:#17324a;border:1px solid #4b83c0;color:#e9eef5}}
.btn-red{{background:#4a1d1d;border:1px solid #8e3b3b;color:#ffe4e4}}
@media (max-width:900px){{.dash-grid{{grid-template-columns:1fr}}.col-span-2{{grid-column:auto}}.op-grid{{grid-template-columns:1fr}}.grid{{grid-template-columns:1fr}}.tabs{{position:static;flex-wrap:wrap;padding:0;background:transparent;backdrop-filter:none}}table{{display:block;overflow:auto;-webkit-overflow-scrolling:touch}}.tl-row{{grid-template-columns:1fr;gap:4px}}}}
</style>
</head>
<body>
<div class='wrap'>
<h1>{html.escape(ui_txt.get('appTitle','Studio Dashboard'))}</h1>
{alert_html}
<div class='tabs'>
  <button id='tabDashBtn' class='tab-btn active' type='button'>{html.escape(ui_txt.get('tabDashboard','대시보드'))}</button>
  <button id='tabMgrBtn' class='tab-btn' type='button'>{html.escape(ui_txt.get('tabCronManager','크론 매니저'))}</button>
</div>

<div id='tabDash' class='tab-panel active'>
  <div class='panel'>
    <h2>{html.escape(sec.get('summary','대시보드 요약'))}</h2>
    <div class='stats'>
      <div class='stat'><div class='k'>전체 jobs</div><div class='v'>{len(jobs)}</div></div>
      <div class='stat'><div class='k'>활성</div><div class='v' style='color:#22c55e'>{enabled_count}</div></div>
      <div class='stat'><div class='k'>비활성</div><div class='v'>{disabled_count}</div></div>
      <div class='stat'><div class='k'>문제 의심</div><div class='v' style='color:{'#ef4444' if problem_count else '#22c55e'}'>{problem_count}</div></div>
      <div class='stat'><div class='k'>Studio UI 정상</div><div class='v' style='color:{'#22c55e' if ui_running else '#ef4444'}'>{ui_running}/{len(ui_rows)}</div></div>
    </div>
  </div>

  <div class='dash-grid'>
    <div class='panel'>
      <h2>Aiven 상태 & 바로가기</h2>
      <div class='stats' style='margin-bottom:10px'>{ui_cards}</div>
      <div class='muted' style='margin-bottom:8px'>mysql-budget 관리 페이지 이동</div>
      <a href='https://console.aiven.io' target='_blank' style='display:inline-block;background:#173b2a;border:1px solid #2aa748;color:#e9eef5;padding:8px 12px;border-radius:8px;text-decoration:none'>Aiven Console 열기</a>
      {ui_err_html}
    </div>

    <div class='panel'>
      <h2>원격 접속 & 포트 복구</h2>
      <div class='stats' style='margin-bottom:10px'>{app_cards_html}</div>
      <div class='muted' style='margin-bottom:8px'>같은 네트워크 접속 주소</div>
      <div style='font-size:12px;line-height:1.6;margin-bottom:10px'>{remote_urls_html}</div>
      <div class='grid' style='grid-template-columns:1fr 1fr;gap:8px'>
        <form method='post' action='/portproxy-refresh'>
          <button class='btn btn-blue'>포트 프록시 갱신</button>
        </form>
        <form method='post' action='/ui-start-all'>
          <button class='btn btn-green'>꺼진 UI 모두 켜기</button>
        </form>
      </div>
    </div>

    <div class='panel'>
      <h2>{html.escape(sec.get('checks','점검 대시보드'))}</h2>
      <table>
        <thead><tr><th>항목</th><th>상태</th><th>상세</th></tr></thead>
        <tbody>{dashboard_check_rows}</tbody>
      </table>
    </div>

    <div class='panel'>
      <h2>{html.escape(sec.get('operations','운영 실행'))}</h2>
      <div class='op-grid'>
        <div class='op-card'>
          <div class='op-title'>런타임 제어</div>
          <div class='op-desc'>현재 상태: <b style='color:{'#22c55e' if rp_on else '#ef4444'}'>{'ON' if rp_on else 'OFF'}</b> · {html.escape(rp_state_text)}</div>
          <div class='grid' style='grid-template-columns:1fr 1fr;gap:8px'>
            <form method='post' action='/rp-on'>
              <button class='btn btn-green'>RP ON</button>
            </form>
            <form method='post' action='/rp-off' onsubmit="return confirm('RP를 끌까?')"> 
              <button class='btn btn-red'>RP OFF</button>
            </form>
          </div>
          <div class='muted' style='margin-top:8px'>Vercel 배포 정리 (tcg 프로젝트 고정)</div>
          <div class='muted' style='font-size:12px;margin-bottom:8px'>dry-run은 삭제 없이 대상만 미리 보여주고, 배포 정리 실행은 실제 삭제해.</div>
          <div class='grid' style='grid-template-columns:1fr 1fr;gap:8px'>
            <form method='post' action='/vercel-cleanup'>
              <button class='btn btn-blue'>배포 정리 실행</button>
            </form>
            <form method='post' action='/vercel-cleanup-dry'>
              <button class='btn'>배포 정리 dry-run</button>
            </form>
          </div>
        </div>

        <form method='post' action='/dm-bulk-delete' class='op-card'>
          <div class='op-title'>DM 일괄 삭제</div>
          <div class='op-desc'>대시보드 전용 실행 · 대상 채널 {html.escape(dm_channel_id)}</div>
          <div class='muted' style='color:{dm_rt_color}'>runtime {dm_rt_label} · {html.escape(dm_rt_detail)}</div>
          <label class='op-label'>삭제 개수</label>
          <input name='limit' type='number' min='1' max='2000' value='300'>
          <label class='op-check'><input name='deletePinned' type='checkbox' value='1' style='width:auto'> 고정 메시지도 삭제</label>
          <button class='btn btn-lime'>DM 일괄 삭제 실행</button>
        </form>

        <form method='post' action='/commit-push' class='op-card'>
          <div class='op-title'>커밋 + 푸시</div>
          <div class='op-desc'>선택한 저장소 변경사항 반영</div>
          <label class='op-label'>대상 저장소</label>
          <select name='target'>
            <option value='workspace'>workspace</option>
            <option value='tcg'>tcg</option>
          </select>
          <label class='op-label'>커밋 메시지</label>
          <input name='message' placeholder='기본값 자동'>
          <button class='btn btn-blue'>커밋 푸시 실행</button>
        </form>

        <form method='post' action='/initial-reset' class='op-card danger' onsubmit="return confirm('이니셜 커밋을 진행할까?')">
          <div class='op-title'>이니셜 커밋으로 밀기</div>
          <div class='op-desc'>선택한 저장소 히스토리 정리 즉시 실행</div>
          <label class='op-label'>대상 저장소</label>
          <select name='target'>
            <option value='workspace'>workspace</option>
            <option value='tcg'>tcg</option>
          </select>
          <label class='op-label'>사유</label>
          <input name='reason' placeholder='reason' value='dashboard requested initial reset'>
          <button class='btn btn-red'>이니셜 커밋으로 밀기</button>
        </form>
      </div>
    </div>

    <div class='panel col-span-2'>
      <h2>{html.escape(sec.get('pin_message','고정 메시지 관리'))}</h2>
      <div class='op-grid'>
        <div class='op-card'>
          <div class='op-title'>고정 메시지 내용 파일</div>
          <div class='op-desc'>{html.escape(str(PIN_MESSAGE_FILE))}</div>
          <div class='muted'>이 파일 수정 후 아래 버튼으로 1회 전송+고정</div>
        </div>
        <form method='post' action='/pin-message' class='op-card'>
          <div class='op-title'>고정 메시지 생성 및 즉시 고정</div>
          <div class='op-desc'>대상 채널: {html.escape(dm_channel_id)}</div>
          <button class='btn btn-blue'>고정 메시지 생성 및 고정</button>
        </form>
      </div>
    </div>
  </div>
</div>

<div id='tabMgr' class='tab-panel'>

  <div class='panel'>
    <h2>{html.escape(sec.get('issues','문제 의심 항목'))}</h2>
    <table>
      <thead><tr><th>이름</th><th>이슈</th></tr></thead>
      <tbody>{''.join(issue_rows)}</tbody>
    </table>
  </div>

  <div class='panel'>
    <h2>{html.escape(sec.get('jobs','작업 목록'))}</h2>
    <div class='grid' style='margin-bottom:10px'>
      <input id='jobSearch' placeholder='작업 검색 (이름/스케줄/상태)'>
      <select id='enabledFilter'>
        <option value='all'>전체</option>
        <option value='on'>활성(on)</option>
        <option value='off'>비활성(off)</option>
      </select>
    </div>
    <table id='jobsTable'>
      <thead><tr>{cron_head_html}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    {err_html}
  </div>
</div>
</div>
<script>
(function(){{
  const q = document.getElementById('jobSearch');
  const f = document.getElementById('enabledFilter');
  const rows = Array.from(document.querySelectorAll('#jobsTable .job-row'));
  function apply(){{
    const keyword = (q?.value || '').toLowerCase().trim();
    const enabled = (f?.value || 'all');
    for (const row of rows){{
      const txt = (row.innerText || '').toLowerCase();
      const rowEnabled = row.dataset.enabled || '';
      const okKeyword = !keyword || txt.includes(keyword);
      const okEnabled = (enabled === 'all') || (rowEnabled === enabled);
      row.style.display = (okKeyword && okEnabled) ? '' : 'none';
    }}
  }}
  q?.addEventListener('input', apply);
  f?.addEventListener('change', apply);

  const tabDashBtn = document.getElementById('tabDashBtn');
  const tabMgrBtn = document.getElementById('tabMgrBtn');
  const tabDash = document.getElementById('tabDash');
  const tabMgr = document.getElementById('tabMgr');
  function openTab(which){{
    const dash = which === 'dash';
    tabDash?.classList.toggle('active', dash);
    tabMgr?.classList.toggle('active', !dash);
    tabDashBtn?.classList.toggle('active', dash);
    tabMgrBtn?.classList.toggle('active', !dash);
  }}
  tabDashBtn?.addEventListener('click', () => openTab('dash'));
  tabMgrBtn?.addEventListener('click', () => openTab('mgr'));
}})();
</script>
</body>
</html>
"""
    return body.encode("utf-8")


def _post_api() -> dict:
    return {
        "val": _val,
        "gateway_call": gateway_call,
        "rp_turn_on": _rp_turn_on,
        "rp_turn_off": _rp_turn_off,
        "load_sources_cfg": _load_sources_cfg,
        "ensure_dm_bulk_runtime": _ensure_dm_bulk_runtime,
        "dm_bulk_delete_enqueue": _dm_bulk_delete_enqueue,
        "commit_push": _commit_push,
        "initial_reset_run": _initial_reset_run,
        "create_and_pin_message": _create_and_pin_message,
        "run_portproxy_update": _run_portproxy_update,
        "start_all_studio_uis": _start_all_studio_uis,
        "cleanup_vercel_deployments": _cleanup_vercel_deployments,
    }


Handler = create_handler(render_page, handle_post, _post_api)


def main() -> int:
    ap = argparse.ArgumentParser(description="Studio dashboard web manager")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8767)
    args = ap.parse_args()

    _ensure_dm_bulk_runtime()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"STUDIO_DASHBOARD:http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
