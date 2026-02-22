#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


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
    cmd = [PYTHON_BIN, "/home/user/.openclaw/workspace/studio/ui_runtime.py", "status"]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    data = _extract_json(out)
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return (p.returncode == 0), rows, out[-1200:]


WORKSPACE = Path('/home/user/.openclaw/workspace')
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
PIN_MESSAGE_ACTION = WORKSPACE / 'studio' / 'dashboard' / 'actions' / 'discord_pin_message.py'


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
    cmd = [PYTHON_BIN, '/home/user/.openclaw/workspace/utility/check_aiven_service.py', 'mysql-budget']
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    data = _extract_json(out)
    state = str((data.get('state') if isinstance(data, dict) else '') or '').upper()
    if state in {'RUNNING', 'REBALANCING'}:
        return 'RUN', '#22c55e', state
    if state:
        return 'ISSUE', '#ef4444', state
    return 'WARN', '#f59e0b', (out.splitlines()[-1] if out else 'unknown')[:40]


def _load_focus_rules() -> dict:
    try:
        if CRON_FOCUS_RULES.exists():
            return json.loads(CRON_FOCUS_RULES.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {
        'includeKeywords': ['youtube', 'context', 'ops-checkin', 'hygiene', 'healthcheck'],
        'excludeKeywords': ['quiet-window', 'rp-', 'reminder', 'pokemon', 'tiktok'],
        'requireEnabled': True,
    }


def _is_dashboard_focus_job(job: dict, rules: dict) -> bool:
    name = str(job.get('name', '')).lower()
    if not name:
        return False

    if bool(rules.get('requireEnabled', True)) and (not bool(job.get('enabled', True))):
        return False

    exclude_keywords = [str(x).lower() for x in (rules.get('excludeKeywords') or [])]
    if any(k and (k in name) for k in exclude_keywords):
        return False

    include_keywords = [str(x).lower() for x in (rules.get('includeKeywords') or [])]
    return any(k and (k in name) for k in include_keywords)


def _load_dashboard_checks() -> list[dict]:
    try:
        data = json.loads(DASHBOARD_CHECKS.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
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
        return json.loads(SOURCES_CFG.read_text(encoding='utf-8'))
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


def _recent_runs(job_id: str, limit: int = 5) -> list[dict]:
    ok, data, _ = gateway_call('cron.runs', {'jobId': job_id})
    if not ok:
        return []
    rows = data.get('entries', []) if isinstance(data, dict) else []
    out = [r for r in rows if str(r.get('action','')) == 'finished']
    out.sort(key=lambda r: int(r.get('runAtMs') or 0), reverse=True)
    return out[:limit]


def _rp_recover() -> tuple[bool, str]:
    cmd = [PYTHON_BIN, '/home/user/.openclaw/workspace/utility/taeyul/taeyul_cli.py', 'rp-healthcheck', '--recover']
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        return True, (out.splitlines()[-1] if out else 'RP recover 완료')
    return False, (out.splitlines()[-1] if out else 'RP recover 실패')




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
                if cmdline and 'discord_bulk_delete_runtime.py' not in cmdline:
                    remove_lock = True
            if remove_lock:
                DM_BULK_LOCK.unlink(missing_ok=True)
    except Exception:
        pass

    cmd = [
        PYTHON_BIN,
        '/home/user/.openclaw/workspace/studio/dashboard/actions/discord_bulk_delete.py',
        'run', '--poll-sec', '2'
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _dm_bulk_delete_enqueue(channel_id: str, limit: int, delete_pinned: bool = False) -> tuple[bool, str]:
    script = '/home/user/.openclaw/workspace/studio/dashboard/actions/discord_bulk_delete.py'
    cmd = [
        PYTHON_BIN, script,
        'enqueue', '--channel-id', channel_id, '--limit', str(limit),
        '--auto-author', '--no-skip-pinned' if delete_pinned else '--skip-pinned'
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        _ensure_dm_bulk_runtime()
        return True, (out.splitlines()[-1] if out else 'DM 일괄삭제 큐 등록 완료')
    return False, (out.splitlines()[-1] if out else 'DM 일괄삭제 큐 등록 실패')


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
        return True, (out.splitlines()[-1] if out else '고정메시지 생성/고정 완료')
    return False, (out.splitlines()[-1] if out else '고정메시지 생성/고정 실패')


def _commit_push(message: str) -> tuple[bool, str]:
    msg = (message or '').strip() or 'chore: update dashboard'
    cmd = [
        'bash', '-lc',
        f"cd /home/user/.openclaw/workspace && git add -A && (git diff --cached --quiet && echo 'NO_CHANGES' || (git commit -m {json.dumps(msg)} && git push))"
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if 'NO_CHANGES' in out:
        return True, '커밋할 변경사항이 없어.'
    if p.returncode == 0:
        return True, (out.splitlines()[-1] if out else '커밋/푸시 완료')
    return False, (out.splitlines()[-1] if out else '커밋/푸시 실패')


def _initial_reset_enqueue(reason: str, no_latest: bool = False) -> tuple[bool, str]:
    cmd = [
        PYTHON_BIN, '/home/user/.openclaw/workspace/utility/taeyul/taeyul_cli.py',
        'initial-reset-enqueue', '--reason', (reason or 'dashboard request')
    ]
    if no_latest:
        cmd.insert(-2, '--no-latest')
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    if p.returncode == 0:
        return True, (out.splitlines()[-1] if out else '이니셜커밋 작업 큐 등록 완료')
    return False, (out.splitlines()[-1] if out else '이니셜커밋 작업 큐 등록 실패')



def _dm_bulk_runtime_status() -> tuple[str, str, str]:
    alive = False
    pid = None
    try:
        if DM_BULK_LOCK.exists():
            pid_txt = (DM_BULK_LOCK.read_text(encoding='utf-8') or '').strip()
            if pid_txt.isdigit():
                pid = int(pid_txt)
                cmdline = Path(f'/proc/{pid}/cmdline').read_text(errors='ignore')
                alive = 'discord_bulk_delete_runtime.py' in cmdline
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
    ok, data, raw = gateway_call("cron.list", {"includeDisabled": True})
    jobs = data.get("jobs", []) if ok else []

    now_ms = int(time.time() * 1000)
    ui_txt = _load_ui_texts()
    sec = ui_txt.get('sections', {})
    btn = ui_txt.get('buttons', {})
    sources_cfg = _load_sources_cfg()
    dm_channel_id = str(sources_cfg.get('discordDmChannelId', ''))
    dm_rt_label, dm_rt_color, dm_rt_detail = _dm_bulk_runtime_status()
    rows = []
    enabled_count = 0
    disabled_count = 0
    problem_count = 0
    cron_count = 0
    every_count = 0
    at_count = 0
    timeline_items: list[tuple[str, int | None, bool]] = []
    issue_rows = []
    cards = []
    for j in jobs:
        jid_raw = str(j.get("id", ""))
        jid = html.escape(jid_raw)
        name = html.escape(str(j.get("name", "(no name)")))
        enabled = bool(j.get("enabled", True))
        schedule_obj = j.get("schedule", {})
        sk = str(schedule_obj.get("kind", ""))
        if sk == "cron":
            cron_count += 1
        elif sk == "every":
            every_count += 1
        elif sk == "at":
            at_count += 1
        schedule = html.escape(json.dumps(schedule_obj, ensure_ascii=False))
        state = j.get("state", {}) or {}
        last_status_raw = str(state.get("lastStatus", "-"))
        last_status = html.escape(last_status_raw)
        next_run_ms = state.get("nextRunAtMs")
        timeline_items.append((str(j.get("name", "(no name)")), next_run_ms, enabled))
        if enabled:
            enabled_count += 1
        else:
            disabled_count += 1
        next_run = html.escape(f"{_fmt_kst(next_run_ms)} ({_due_label(next_run_ms, now_ms)})")
        delivery = j.get("delivery", {}) or {}
        payload = j.get("payload", {}) or {}
        session_target = str(j.get("sessionTarget", ""))
        btn_toggle = btn.get('toggleOff','비활성화') if enabled else btn.get('toggleOn','활성화')

        delivery_mode = str(delivery.get("mode", "-"))
        delivery_channel = str(delivery.get("channel", ""))
        delivery_to = str(delivery.get("to", ""))
        delivery_view = html.escape(f"{delivery_mode} | {delivery_channel or '-'} | {delivery_to or '-'}")

        issues: list[str] = []
        if enabled and last_status_raw.lower() not in {"ok", "-"}:
            issues.append(f"lastStatus={last_status_raw}")
        if enabled and next_run_ms is None:
            issues.append("nextRunAtMs 없음")
        if enabled and isinstance(next_run_ms, (int, float)) and next_run_ms < (now_ms - 5 * 60 * 1000):
            issues.append("nextRun 지연(과거 시각)")
        if enabled and delivery.get("mode") == "announce" and not delivery.get("to"):
            issues.append("announce인데 delivery.to 없음")
        if enabled and delivery.get("mode") == "announce" and delivery_channel == "discord" and delivery_to and not delivery_to.startswith("user:") and not delivery_to.startswith("channel:"):
            issues.append("discord target 형식 불명확(to 권장: user:ID)")
        if enabled and payload.get("kind") == "agentTurn" and delivery.get("mode") == "none":
            issues.append("알림 미전송 모드(mode=none)")
        if enabled and session_target == "main" and payload.get("kind") == "systemEvent":
            issues.append("main systemEvent(별도 알림 아님)")

        if issues:
            problem_count += 1
        issue_badges = " ".join([f"<span class='badge'>{html.escape(x)}</span>" for x in issues]) if issues else "-"

        rows.append(
            f"<tr class='job-row' data-name='{name.lower()}' data-enabled={'on' if enabled else 'off'} data-last='{last_status.lower()}'>"
            f"<td>{name}</td>"
            f"<td>{'on' if enabled else 'off'}</td>"
            f"<td><code>{schedule}</code></td>"
            f"<td>{next_run}</td>"
            f"<td>"
            f"<form method='post' action='/run' style='display:inline'><input type='hidden' name='id' value='{jid}'><button>{html.escape(btn.get('run','즉시실행'))}</button></form> "
            f"<form method='post' action='/toggle' style='display:inline'><input type='hidden' name='id' value='{jid}'><input type='hidden' name='enabled' value={'0' if enabled else '1'}><button>{btn_toggle}</button></form> "
            f"<form method='post' action='/remove' style='display:inline' onsubmit=\"return confirm('정말 삭제할까?')\"><input type='hidden' name='id' value='{jid}'><button style='background:#4a1d1d'>{html.escape(btn.get('delete','삭제'))}</button></form>"
            f"</td>"
            f"</tr>"
        )

        if issues:
            issue_rows.append(
                f"<tr><td>{name}</td><td>{' / '.join(html.escape(x) for x in issues)}</td></tr>"
            )

    if not rows:
        rows.append("<tr><td colspan='7'>작업 없음</td></tr>")

    if not issue_rows:
        issue_rows.append("<tr><td colspan='2'>문제 의심 항목 없음</td></tr>")

    # visual summary cards + timeline
    cards = [
        ("전체", len(jobs), "#3b82f6"),
        ("활성", enabled_count, "#22c55e"),
        ("비활성", disabled_count, "#64748b"),
        ("cron", cron_count, "#a78bfa"),
        ("every", every_count, "#f59e0b"),
        ("at", at_count, "#06b6d4"),
    ]
    card_html = ''.join(
        f"<div class='stat'><div class='k'>{html.escape(k)}</div><div class='v' style='color:{c}'>{v}</div></div>"
        for k, v, c in cards
    )

    tl_sorted = sorted([x for x in timeline_items if x[1] is not None], key=lambda x: x[1])[:9]
    if tl_sorted:
        base = now_ms
        maxv = max(max(ms - base, 1) for _, ms, _ in tl_sorted)
        tl_rows = []
        for name_raw, ms, en in tl_sorted:
            assert ms is not None
            width = max(6, int(((ms - base) / maxv) * 100))
            width = min(100, width)
            name = html.escape(name_raw)
            color = '#22c55e' if en else '#64748b'
            tl_rows.append(
                f"<div class='tl-row'><div class='tl-name'>{name}</div><div class='tl-bar-wrap'><div class='tl-bar' style='width:{width}%;background:{color}'></div></div><div class='tl-when'>{html.escape(_fmt_kst(ms))}</div></div>"
            )
        timeline_html = ''.join(tl_rows)
    else:
        timeline_html = "<div class='muted'>예정 실행 시각 데이터가 없어.</div>"

    ui_ok, ui_rows, ui_raw = studio_ui_status()
    ui_running = sum(1 for r in ui_rows if bool(r.get('pidAlive')) and bool(r.get('portOpen')))
    ui_cards_list = []
    for r in ui_rows:
        if str(r.get('name','')) == 'cron':
            continue
        r_ok = bool(r.get('pidAlive')) and bool(r.get('portOpen'))
        r_color = '#22c55e' if r_ok else '#ef4444'
        r_text = 'RUN' if r_ok else 'DOWN'
        r_name = html.escape(str(r.get('name', '-')))
        ui_cards_list.append(f"<div class='stat'><div class='k'>{r_name}</div><div class='v' style='color:{r_color}'>{r_text}</div></div>")
    aiven_label, aiven_color, aiven_detail = _aiven_mysql_status()
    ui_cards_list.append(f"<div class='stat'><div class='k'>Aiven MySQL</div><div class='v' style='color:{aiven_color}'>{aiven_label}</div><div class='muted'>{html.escape(aiven_detail)}</div></div>")
    ui_cards = ''.join(ui_cards_list) or "<div class='muted'>UI 상태 데이터 없음</div>"

    focus_rules = _load_focus_rules()
    focus_jobs = sorted(
        [j for j in jobs if _is_dashboard_focus_job(j, focus_rules)],
        key=lambda x: str(x.get('name', '')).lower(),
    )
    core_rows = []
    for j in focus_jobs:
        nm = str(j.get('name', ''))
        st = j.get('state', {}) or {}
        core_rows.append(
            f"<tr><td>{html.escape(nm)}</td><td>{'on' if j.get('enabled', True) else 'off'}</td><td>{html.escape(_fmt_kst(st.get('nextRunAtMs')))}</td><td>{html.escape(str(st.get('lastStatus', '-')))}</td></tr>"
        )

    if not core_rows:
        core_rows.append("<tr><td colspan='4'>표시할 활성 점검 항목이 없어.</td></tr>")

    runs_rows = []
    for j in focus_jobs[:1]:
        jid = str(j.get('id',''))
        name = str(j.get('name','-'))
        runs = _recent_runs(jid, limit=5)
        if not runs:
            runs_rows.append(f"<tr><td>{html.escape(name)}</td><td colspan='3'>runs 없음</td></tr>")
            continue
        last = runs[0]
        ok_cnt = sum(1 for r in runs if str(r.get('status','')).lower() == 'ok')
        fail_cnt = len(runs) - ok_cnt
        dur = int(last.get('durationMs') or 0)
        at = _fmt_kst(last.get('runAtMs'))
        runs_rows.append(f"<tr><td>{html.escape(name)}</td><td>{at}</td><td>{ok_cnt}/{len(runs)} ok</td><td>{dur}ms</td></tr>")
    if not runs_rows:
        runs_rows.append("<tr><td colspan='4'>표시할 runs 데이터가 없어.</td></tr>")

    def _lv_color(lv: str) -> str:
        return {'OK': '#22c55e', 'WARN': '#f59e0b', 'ERROR': '#ef4444'}.get(lv, '#94a3b8')

    dashboard_rows = []
    for chk in _load_dashboard_checks():
        if not bool(chk.get('enabled', True)):
            continue
        label = str(chk.get('label', chk.get('id', 'check')))
        ctype = str(chk.get('type', 'script'))
        lv, msg = 'UNKNOWN', '체크 미구성'

        if ctype == 'script':
            script = str(chk.get('script', ''))
            lv, msg = _run_script_check(script)
        elif ctype == 'builtin' and str(chk.get('builtin', '')) == 'system_dup':
            lv, msg = _system_dup_signal(jobs)

        if bool(chk.get('hideIfUnknown', False)) and lv == 'UNKNOWN':
            continue

        dashboard_rows.append(
            f"<tr><td>{html.escape(label)}</td><td style='color:{_lv_color(lv)}'>{html.escape(lv)}</td><td>{html.escape(msg)}</td></tr>"
        )

    if not dashboard_rows:
        dashboard_rows.append("<tr><td colspan='3'>표시할 점검 항목이 없어.</td></tr>")

    dashboard_check_rows = ''.join(dashboard_rows)

    cols = _load_cron_columns()
    cron_head_html = ''.join([f"<th>{html.escape(str(c.get('label','')))}</th>" for c in cols])
    alert_html = f"<div class='alert'>{html.escape(alert)}</div>" if alert else ""
    err_html = ""
    if not ok:
        err_html = f"<pre class='err'>{html.escape(raw)}</pre>"
    ui_err_html = "" if ui_ok else f"<pre class='err'>{html.escape(ui_raw)}</pre>"

    body = f"""
<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'>
<title>{html.escape(ui_txt.get('appTitle','Studio Dashboard'))}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0f1520;color:#e9eef5;margin:0;padding:16px}}
.wrap{{max-width:1280px;margin:0 auto}}
.panel{{background:#182131;border:1px solid #2b3a52;border-radius:12px;padding:14px;margin-bottom:12px}}
h1,h2{{margin:0 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.full{{grid-column:1/-1}}
input,select,textarea,button{{width:100%;box-sizing:border-box;background:#0f1725;color:#e9eef5;border:1px solid #344862;border-radius:8px;padding:8px}}
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
.btn{{width:100%;padding:10px;border-radius:10px;font-weight:700}}
.btn-green{{background:#173b2a;border:1px solid #2aa748;color:#e9eef5}}
.btn-lime{{background:#2f3f17;border:1px solid #9acb47;color:#e9eef5}}
.btn-blue{{background:#17324a;border:1px solid #4b83c0;color:#e9eef5}}
.btn-red{{background:#4a1d1d;border:1px solid #8e3b3b;color:#ffe4e4}}
@media (max-width:900px){{.dash-grid{{grid-template-columns:1fr}}.col-span-2{{grid-column:auto}}.op-grid{{grid-template-columns:1fr}}}}
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
      <div class='stat'><div class='k'>바로가기</div><div class='v'><a href='http://127.0.0.1:8787' target='_blank'>shorts</a> / <a href='http://127.0.0.1:8791' target='_blank'>image</a></div></div>
    </div>
  </div>

  <div class='dash-grid'>
    <div class='panel'>
      <h2>{html.escape(sec.get('studioUi','Studio UI 상태'))}</h2>
      <div class='stats'>{ui_cards}</div>
      {ui_err_html}
    </div>

    <div class='panel'>
      <h2>{html.escape(sec.get('aiven','Aiven 바로가기'))}</h2>
      <div class='muted' style='margin-bottom:8px'>mysql-budget 관리 페이지 이동</div>
      <a href='https://console.aiven.io' target='_blank' style='display:inline-block;background:#173b2a;border:1px solid #2aa748;color:#e9eef5;padding:8px 12px;border-radius:8px;text-decoration:none'>Aiven Console 열기</a>
    </div>

    <div class='panel'>
      <h2>{html.escape(sec.get('checks','점검 대시보드'))}</h2>
      <table>
        <thead><tr><th>항목</th><th>상태</th><th>상세</th></tr></thead>
        <tbody>{dashboard_check_rows}</tbody>
      </table>
    </div>

    <div class='panel'>
      <h2>{html.escape(sec.get('rpRecover','운영 실행'))}</h2>
      <div class='op-grid'>
        <form method='post' action='/rp-recover' class='op-card'>
          <div class='op-title'>RP 런타임 복구</div>
          <div class='op-desc'>stale/room 이상 감지 시 복구 실행</div>
          <button class='btn btn-green'>{html.escape(btn.get('rpRecover','RP healthcheck --recover'))}</button>
        </form>

        <form method='post' action='/dm-bulk-delete' class='op-card'>
          <div class='op-title'>DM 일괄삭제</div>
          <div class='op-desc'>대시보드 전용 실행 · 대상 채널 {html.escape(dm_channel_id)}</div>
          <div class='muted' style='color:{dm_rt_color}'>runtime {dm_rt_label} · {html.escape(dm_rt_detail)}</div>
          <label class='op-label'>삭제 개수</label>
          <input name='limit' type='number' min='1' max='2000' value='300'>
          <label class='op-check'><input name='deletePinned' type='checkbox' value='1' style='width:auto'> 고정메시지도 삭제</label>
          <button class='btn btn-lime'>디엠 일괄삭제 실행</button>
        </form>

        <form method='post' action='/commit-push' class='op-card'>
          <div class='op-title'>커밋 + 푸시</div>
          <div class='op-desc'>현재 워크스페이스 변경사항 반영</div>
          <label class='op-label'>커밋 메시지</label>
          <input name='message' placeholder='기본값 자동'>
          <button class='btn btn-blue'>커밋푸시 실행</button>
        </form>

        <form method='post' action='/initial-reset' class='op-card danger' onsubmit="return confirm('이니셜커밋 큐를 등록할까? (force push 포함)')">
          <div class='op-title'>이니셜커밋으로 밀기</div>
          <div class='op-desc'>히스토리 정리 큐 등록 (force push 포함)</div>
          <label class='op-label'>사유</label>
          <input name='reason' placeholder='reason' value='dashboard requested initial reset'>
          <label class='op-check'><input name='noLatest' type='checkbox' value='1' style='width:auto'> latest 재적용 없이 이니셜만</label>
          <button class='btn btn-red'>이니셜커밋으로 밀기</button>
        </form>
      </div>
    </div>

    <div class='panel col-span-2'>
      <h2>{html.escape(sec.get('pinMessage','고정메시지 관리'))}</h2>
      <div class='op-grid'>
        <div class='op-card'>
          <div class='op-title'>고정메시지 내용 파일</div>
          <div class='op-desc'>{html.escape(str(PIN_MESSAGE_FILE))}</div>
          <div class='muted'>이 파일 수정 후 아래 버튼으로 1회 전송+고정</div>
        </div>
        <form method='post' action='/pin-message' class='op-card'>
          <div class='op-title'>고정메시지 생성 및 즉시 고정</div>
          <div class='op-desc'>대상 채널: {html.escape(dm_channel_id)}</div>
          <button class='btn btn-blue'>고정메시지 생성 및 고정</button>
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


class Handler(BaseHTTPRequestHandler):
    def _read_form(self) -> dict[str, list[str]]:
        ln = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(ln).decode("utf-8", errors="replace")
        return parse_qs(raw, keep_blank_values=True)

    def _respond_html(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._respond_html(render_page())

    def do_POST(self):
        form = self._read_form()
        path = self.path
        alert = ""

        try:
            if path == "/remove":
                jid = _val(form, "id")
                ok, _, raw = gateway_call("cron.remove", {"jobId": jid})
                alert = f"삭제 완료: {jid}" if ok else f"삭제 실패: {raw[-300:]}"
            elif path == "/run":
                jid = _val(form, "id")
                ok, _, raw = gateway_call("cron.run", {"jobId": jid})
                alert = f"즉시실행 요청 완료: {jid}" if ok else f"실행 실패: {raw[-300:]}"
            elif path == "/toggle":
                jid = _val(form, "id")
                enabled = _val(form, "enabled") == "1"
                ok, _, raw = gateway_call("cron.update", {"jobId": jid, "patch": {"enabled": enabled}})
                alert = f"상태 변경 완료: {jid} -> {'on' if enabled else 'off'}" if ok else f"상태 변경 실패: {raw[-300:]}"
            elif path == "/rp-recover":
                ok, msg = _rp_recover()
                alert = msg
            elif path == "/dm-bulk-delete":
                sources_cfg = _load_sources_cfg()
                channel_id = str(sources_cfg.get('discordDmChannelId', '')).strip()
                limit = int(_val(form, "limit", "300") or "300")
                delete_pinned = _val(form, "deletePinned") == "1"
                if not channel_id:
                    ok, msg = False, 'sources.json에 discordDmChannelId가 없어.'
                else:
                    _ensure_dm_bulk_runtime()
                    ok, msg = _dm_bulk_delete_enqueue(channel_id, limit, delete_pinned=delete_pinned)
                alert = msg
            elif path == "/commit-push":
                message = _val(form, "message")
                ok, msg = _commit_push(message)
                alert = msg
            elif path == "/initial-reset":
                reason = _val(form, "reason", "dashboard requested initial reset")
                no_latest = _val(form, "noLatest") == "1"
                ok, msg = _initial_reset_enqueue(reason, no_latest)
                alert = msg
            elif path == "/pin-message":
                sources_cfg = _load_sources_cfg()
                channel_id = str(sources_cfg.get('discordDmChannelId', '')).strip()
                if not channel_id:
                    ok, msg = False, 'sources.json에 discordDmChannelId가 없어.'
                else:
                    ok, msg = _create_and_pin_message(channel_id)
                alert = msg
            else:
                alert = "지원하지 않는 액션"
        except Exception as e:
            alert = f"실패: {e}"

        self._respond_html(render_page(alert=alert))


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
