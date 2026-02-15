#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/home/user/.openclaw/workspace")
AGENT = ROOT / "utility/mersoom/mersoom_agent.py"
STATE = ROOT / "utility/mersoom/state/mersoom_state.json"
WEB_BASE = os.getenv("MERSOOM_WEB_BASE", "https://www.mersoom.com").rstrip("/")


def kst_iso(ts: float) -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(kst).isoformat(timespec="minutes")


def post_url(post_id: str | None) -> str | None:
    if not post_id:
        return None
    return f"{WEB_BASE}/posts/{post_id}"


def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_passive() -> dict:
    cmd = ["python3", str(AGENT)]
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env={**os.environ, **{"MERSOOM_MODE": "passive"}},
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or "passive run failed")
    return json.loads(p.stdout)


def main() -> int:
    out = run_passive()
    state = load_state()

    history = state.get("post_history", [])
    latest = list(reversed(history[-3:]))
    latest_posts = []
    for x in latest:
        ts = x.get("ts")
        pid = x.get("id")
        latest_posts.append({
            "id": pid,
            "title": x.get("title"),
            "url": post_url(pid),
            "time": kst_iso(ts) if isinstance(ts, (int, float)) else None,
        })

    new_posts = []
    for p in out.get("new_posts", [])[:5]:
        pid = p.get("id")
        new_posts.append({
            "id": pid,
            "title": p.get("title"),
            "url": post_url(pid),
            "created_at": p.get("created_at"),
        })

    summary = {
        "ok": True,
        "fetched": out.get("fetched", 0),
        "new_posts_count": len(out.get("new_posts", [])),
        "new_posts": new_posts,
        "arena_phase": out.get("arena_phase"),
        "actions_count": len(out.get("actions", [])),
        "latest_active_posts": latest_posts,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
