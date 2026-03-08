from __future__ import annotations

import html
import json
import time


def build_dashboard_context(alert: str, api: dict) -> dict:
    gateway_call = api["gateway_call"]
    load_ui_texts = api["load_ui_texts"]
    load_sources_cfg = api["load_sources_cfg"]
    dm_bulk_runtime_status = api["dm_bulk_runtime_status"]
    rp_status = api["rp_status"]
    studio_ui_status = api["studio_ui_status"]
    aiven_mysql_status = api["aiven_mysql_status"]
    load_network_cfg = api["load_network_cfg"]
    load_dashboard_checks = api["load_dashboard_checks"]
    run_script_check = api["run_script_check"]
    system_dup_signal = api["system_dup_signal"]
    load_cron_columns = api["load_cron_columns"]
    fmt_kst = api["fmt_kst"]
    due_label = api["due_label"]

    ok, data, raw = gateway_call("cron.list", {"includeDisabled": True})
    jobs = data.get("jobs", []) if ok else []

    now_ms = int(time.time() * 1000)
    ui_txt = load_ui_texts()
    sec = ui_txt.get('sections', {})
    btn = ui_txt.get('buttons', {})
    sources_cfg = load_sources_cfg()
    dm_channel_id = str(sources_cfg.get('discordDmChannelId', ''))
    dm_rt_label, dm_rt_color, dm_rt_detail = dm_bulk_runtime_status()
    rp_on, rp_state_text = rp_status()

    rows = []
    enabled_count = 0
    disabled_count = 0
    problem_count = 0
    issue_rows = []

    for j in jobs:
        jid_raw = str(j.get("id", ""))
        jid = html.escape(jid_raw)
        name = html.escape(str(j.get("name", "(no name)")))
        enabled = bool(j.get("enabled", True))
        schedule_obj = j.get("schedule", {})
        schedule = html.escape(json.dumps(schedule_obj, ensure_ascii=False))
        state = j.get("state", {}) or {}
        last_status_raw = str(state.get("lastStatus", "-"))
        last_status = html.escape(last_status_raw)
        next_run_ms = state.get("nextRunAtMs")
        if enabled:
            enabled_count += 1
        else:
            disabled_count += 1
        next_run = html.escape(f"{fmt_kst(next_run_ms)} ({due_label(next_run_ms, now_ms)})")
        delivery = j.get("delivery", {}) or {}
        payload = j.get("payload", {}) or {}
        session_target = str(j.get("sessionTarget", ""))
        btn_toggle = btn.get('toggleOff', '비활성화') if enabled else btn.get('toggleOn', '활성화')

        delivery_channel = str(delivery.get("channel", ""))

        issues: list[str] = []
        if enabled and last_status_raw.lower() not in {"ok", "-"}:
            issues.append(f"lastStatus={last_status_raw}")
        if enabled and next_run_ms is None:
            issues.append("nextRunAtMs 없음")
        if enabled and isinstance(next_run_ms, (int, float)) and next_run_ms < (now_ms - 5 * 60 * 1000):
            issues.append("nextRun 지연(과거 시각)")
        if enabled and delivery.get("mode") == "announce" and not delivery.get("to"):
            issues.append("announce인데 delivery.to 없음")
        if enabled and delivery.get("mode") == "announce" and delivery_channel == "discord" and delivery.get("to") and not str(delivery.get("to")).startswith("user:") and not str(delivery.get("to")).startswith("channel:"):
            issues.append("discord target 형식 불명확(to 권장: user:ID)")
        if enabled and payload.get("kind") == "agentTurn" and delivery.get("mode") == "none":
            issues.append("알림 미전송 모드(mode=none)")
        if enabled and session_target == "main" and payload.get("kind") == "systemEvent":
            issues.append("main systemEvent(별도 알림 아님)")

        if issues:
            problem_count += 1

        rows.append(
            f"<tr class='job-row' data-name='{name.lower()}' data-enabled={'on' if enabled else 'off'} data-last='{last_status.lower()}'>"
            f"<td>{name}</td>"
            f"<td>{'on' if enabled else 'off'}</td>"
            f"<td><code>{schedule}</code></td>"
            f"<td>{next_run}</td>"
            f"<td>"
            f"<form method='post' action='/run' style='display:inline'><input type='hidden' name='id' value='{jid}'><button>{html.escape(btn.get('run','즉시 실행'))}</button></form> "
            f"<form method='post' action='/toggle' style='display:inline'><input type='hidden' name='id' value='{jid}'><input type='hidden' name='enabled' value={'0' if enabled else '1'}><button>{btn_toggle}</button></form> "
            f"<form method='post' action='/remove' style='display:inline' onsubmit=\"return confirm('정말 삭제할까?')\"><input type='hidden' name='id' value='{jid}'><button style='background:#4a1d1d'>{html.escape(btn.get('delete','삭제'))}</button></form>"
            f"</td>"
            f"</tr>"
        )

        if issues:
            issue_rows.append(f"<tr><td>{name}</td><td>{' / '.join(html.escape(x) for x in issues)}</td></tr>")

    if not rows:
        rows.append("<tr><td colspan='7'>작업 없음</td></tr>")
    if not issue_rows:
        issue_rows.append("<tr><td colspan='2'>문제 의심 항목 없음</td></tr>")

    ui_ok, ui_rows, ui_raw = studio_ui_status()
    ui_running = sum(1 for r in ui_rows if bool(r.get('pidAlive')) and bool(r.get('portOpen')))
    ui_cards_list = []
    app_cards_list = []
    for r in ui_rows:
        nm = str(r.get('name', ''))
        if nm == 'cron':
            continue
        r_ok = bool(r.get('pidAlive')) and bool(r.get('portOpen'))
        r_color = '#22c55e' if r_ok else '#ef4444'
        r_text = 'RUN' if r_ok else 'DOWN'
        r_name = html.escape(str(r.get('name', '-')))
        if nm in {'shorts', 'image', 'music'}:
            app_cards_list.append(f"<div class='stat'><div class='k'>{r_name}</div><div class='v' style='color:{r_color}'>{r_text}</div></div>")
            continue
        ui_cards_list.append(f"<div class='stat'><div class='k'>{r_name}</div><div class='v' style='color:{r_color}'>{r_text}</div></div>")

    aiven_label, aiven_color, aiven_detail = aiven_mysql_status()
    ui_cards_list.append(f"<div class='stat'><div class='v' style='color:{aiven_color}'>{aiven_label}</div><div class='muted'>{html.escape(aiven_detail)}</div></div>")
    ui_cards = ''.join(ui_cards_list) or "<div class='muted'>UI 상태 데이터 없음</div>"

    ncfg = load_network_cfg()
    nip = str(ncfg.get('lanHostIp', '') or '').strip()
    nhost = str(ncfg.get('hostName', '') or '').strip()
    link_lines = []
    ports_map = api["ui_ports"]()
    for label, port in [('dashboard', ports_map['cron']), ('shorts', ports_map['shorts']), ('image', ports_map['image']), ('music', ports_map['music'])]:
        links = []
        if nip:
            u = f"http://{nip}:{port}"
            links.append(f"<a href='{html.escape(u)}' target='_blank'>{html.escape(u)}</a>")
        if nhost:
            u = f"http://{nhost}:{port}"
            links.append(f"<a href='{html.escape(u)}' target='_blank'>{html.escape(u)}</a>")
        if links:
            link_lines.append(f"<div><b>{label}</b> · " + " / ".join(links) + "</div>")

    remote_urls_html = ''.join(link_lines) or "<div class='muted'>network.json의 lanHostIp를 채우면 바로 링크가 보여.</div>"
    app_cards_html = ''.join(app_cards_list) or "<div class='muted'>shorts/image 상태 데이터 없음</div>"

    def _lv_color(lv: str) -> str:
        return {'OK': '#22c55e', 'WARN': '#f59e0b', 'ERROR': '#ef4444'}.get(lv, '#94a3b8')

    dashboard_rows = []
    for chk in load_dashboard_checks():
        if not bool(chk.get('enabled', True)):
            continue
        label = str(chk.get('label', chk.get('id', 'check')))
        ctype = str(chk.get('type', 'script'))
        lv, msg = 'UNKNOWN', '체크 미구성'

        if ctype == 'script':
            script = str(chk.get('script', ''))
            lv, msg = run_script_check(script)
        elif ctype == 'builtin' and str(chk.get('builtin', '')) == 'system_dup':
            lv, msg = system_dup_signal(jobs)

        if bool(chk.get('hideIfUnknown', False)) and lv == 'UNKNOWN':
            continue

        dashboard_rows.append(
            f"<tr><td>{html.escape(label)}</td><td style='color:{_lv_color(lv)}'>{html.escape(lv)}</td><td>{html.escape(msg)}</td></tr>"
        )

    if not dashboard_rows:
        dashboard_rows.append("<tr><td colspan='3'>표시할 점검 항목이 없어.</td></tr>")

    dashboard_check_rows = ''.join(dashboard_rows)

    cols = load_cron_columns()
    cron_head_html = ''.join([f"<th>{html.escape(str(c.get('label', '')))}</th>" for c in cols])
    alert_html = f"<div class='alert'>{html.escape(alert)}</div>" if alert else ""
    err_html = "" if ok else f"<pre class='err'>{html.escape(raw)}</pre>"
    ui_err_html = "" if ui_ok else f"<pre class='err'>{html.escape(ui_raw)}</pre>"

    return {
        'jobs': jobs,
        'ui_txt': ui_txt,
        'sec': sec,
        'dm_channel_id': dm_channel_id,
        'dm_rt_label': dm_rt_label,
        'dm_rt_color': dm_rt_color,
        'dm_rt_detail': dm_rt_detail,
        'rp_on': rp_on,
        'rp_state_text': rp_state_text,
        'rows': rows,
        'enabled_count': enabled_count,
        'disabled_count': disabled_count,
        'problem_count': problem_count,
        'issue_rows': issue_rows,
        'ui_running': ui_running,
        'ui_rows': ui_rows,
        'ui_cards': ui_cards,
        'ui_err_html': ui_err_html,
        'app_cards_html': app_cards_html,
        'remote_urls_html': remote_urls_html,
        'dashboard_check_rows': dashboard_check_rows,
        'cron_head_html': cron_head_html,
        'alert_html': alert_html,
        'err_html': err_html,
    }
