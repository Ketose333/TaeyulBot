from __future__ import annotations


def handle_post(path: str, form: dict[str, list[str]], api: dict) -> str:
    """Dashboard POST action router (phase-1 split)."""
    val = api["val"]

    try:
        if path == "/remove":
            jid = val(form, "id")
            ok, _, raw = api["gateway_call"]("cron.remove", {"jobId": jid})
            return f"삭제 완료: {jid}" if ok else f"삭제 실패: {raw[-300:]}"

        if path == "/run":
            jid = val(form, "id")
            ok, _, raw = api["gateway_call"]("cron.run", {"jobId": jid})
            return f"즉시 실행 요청 완료: {jid}" if ok else f"실행 실패: {raw[-300:]}"

        if path == "/toggle":
            jid = val(form, "id")
            enabled = val(form, "enabled") == "1"
            ok, _, raw = api["gateway_call"]("cron.update", {"jobId": jid, "patch": {"enabled": enabled}})
            return f"상태 변경 완료: {jid} -> {'on' if enabled else 'off'}" if ok else f"상태 변경 실패: {raw[-300:]}"

        if path == "/rp-on":
            _, msg = api["rp_turn_on"]()
            return msg

        if path == "/rp-off":
            _, msg = api["rp_turn_off"]()
            return msg

        if path == "/dm-bulk-delete":
            sources_cfg = api["load_sources_cfg"]()
            channel_id = str(sources_cfg.get('discordDmChannelId', '')).strip()
            limit = int(val(form, "limit", "300") or "300")
            delete_pinned = val(form, "deletePinned") == "1"
            if not channel_id:
                return 'sources.json에 discordDmChannelId가 없어.'
            api["ensure_dm_bulk_runtime"]()
            _, msg = api["dm_bulk_delete_enqueue"](channel_id, limit, delete_pinned=delete_pinned)
            return msg

        if path == "/commit-push":
            message = val(form, "message")
            target = val(form, "target", "workspace")
            if target not in {"workspace", "tcg"}:
                target = "workspace"
            _, msg = api["commit_push"](message, target)
            return msg

        if path == "/initial-reset":
            reason = val(form, "reason", "dashboard requested initial reset")
            target = val(form, "target", "workspace")
            if target not in {"workspace", "tcg"}:
                target = "workspace"
            _, msg = api["initial_reset_run"](reason, target)
            return msg

        if path == "/pin-message":
            sources_cfg = api["load_sources_cfg"]()
            channel_id = str(sources_cfg.get('discordDmChannelId', '')).strip()
            if not channel_id:
                return 'sources.json에 discordDmChannelId가 없어.'
            _, msg = api["create_and_pin_message"](channel_id)
            return msg

        if path == "/portproxy-refresh":
            _, msg = api["run_portproxy_update"]()
            return msg

        if path == "/ui-start-all":
            _, msg = api["start_all_studio_uis"]()
            return msg

        if path == "/vercel-cleanup":
            _, msg = api["cleanup_vercel_deployments"](False)
            return msg

        if path == "/vercel-cleanup-dry":
            _, msg = api["cleanup_vercel_deployments"](True)
            return msg

        return "지원하지 않는 액션"

    except Exception as e:
        return f"실패: {e}"
