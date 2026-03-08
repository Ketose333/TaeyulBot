#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from utility.common.generation_defaults import WORKSPACE_ROOT
from utility.common.youtube_watch_paths import channel_state_path

ROOT = WORKSPACE_ROOT


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(default)
    except Exception:
        return dict(default)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _extract_post_ids(html: str) -> list[str]:
    ids: list[str] = []

    for pid in re.findall(r"/post/([A-Za-z0-9_-]{8,})", html):
        if pid not in ids:
            ids.append(pid)

    for pid in re.findall(r'"postId"\s*:\s*"([A-Za-z0-9_-]{8,})"', html):
        if pid not in ids:
            ids.append(pid)

    return ids


def _to_post_url(post_id: str) -> str:
    # 사용자 합의 포맷: http://youtube.com/post/<id>
    return f"http://youtube.com/post/{post_id}"


def _extract_post_id_from_url(url: str) -> str | None:
    m = re.search(r"/post/([A-Za-z0-9_-]{8,})", url)
    return m.group(1) if m else None


def run_idntt_community() -> int:
    community_url = "https://www.youtube.com/@idntt/community"
    state_path = channel_state_path("idntt-community")

    req = Request(
        community_url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
        },
    )
    with urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    state = _load_json(state_path, {"last_checked_at": None, "seen_urls": []})
    raw_seen_urls = state.get("seen_urls", [])
    seen_post_ids: list[str] = []
    if isinstance(raw_seen_urls, list):
        for item in raw_seen_urls:
            pid = _extract_post_id_from_url(str(item))
            if pid and pid not in seen_post_ids:
                seen_post_ids.append(pid)

    extracted_post_ids = _extract_post_ids(html)
    newest_unseen_id = next((pid for pid in extracted_post_ids if pid not in seen_post_ids), None)

    merged_ids: list[str] = []
    for pid in extracted_post_ids + seen_post_ids:
        if pid not in merged_ids:
            merged_ids.append(pid)

    state["last_checked_at"] = _now_iso()
    state["seen_urls"] = [_to_post_url(pid) for pid in merged_ids[:30]]
    _save_json(state_path, state)

    if newest_unseen_id:
        print("이 글 한번 볼래?")
        print(_to_post_url(newest_unseen_id))
    else:
        print("NO_REPLY")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified YouTube watch helper")
    parser.add_argument(
        "--task",
        choices=["idntt-community"],
        default="idntt-community",
        help="Watch task to run",
    )
    args = parser.parse_args()

    if args.task == "idntt-community":
        return run_idntt_community()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
