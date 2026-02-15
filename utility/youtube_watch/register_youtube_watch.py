#!/usr/bin/env python3
"""YouTube 채널 업로드(쇼츠 포함) 디스코드 DM 알림용 크론 payload 생성/관리 유틸리티.

사용 예시:
  python3 utility/youtube_watch/register_youtube_watch.py \
    --channel-id UCmnuDfK6fqL2hIWKjAmXJ-Q \
    --target 753783778157264936

  python3 utility/youtube_watch/register_youtube_watch.py \
    --channel-id UCxxxx --target 1234 --interval-min 10 --save
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

WORKSPACE = Path("/home/user/.openclaw/workspace")
STATE_DIR = WORKSPACE / "utility" / "youtube_watch" / "state"
REGISTRY_PATH = STATE_DIR / "channels.json"


@dataclass
class WatchConfig:
    channel_id: str
    target: str
    interval_min: int = 15

    @property
    def state_file(self) -> str:
        return f"/home/user/.openclaw/workspace/memory/youtube-watch-{self.channel_id}.json"

    @property
    def feed_url(self) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"

    @property
    def job_name(self) -> str:
        return f"YouTube new uploads alert - {self.channel_id}"


def build_agent_turn_message(cfg: WatchConfig) -> str:
    return (
        f"Check this YouTube channel feed for new uploads (including Shorts): {cfg.feed_url}\n\n"
        "Rules:\n"
        f"1) Use a state file at {cfg.state_file}\n"
        "2) Fetch the feed and parse entry IDs/links/published/title.\n"
        "3) On first run, initialize state with the latest video ID and do not notify.\n"
        "4) On later runs, if new video IDs appear since last seen, send Discord DM for each new item in chronological order (oldest->newest) via message tool:\n"
        "   - channel: discord\n"
        "   - action: send\n"
        f"   - target: {cfg.target}\n"
        "   - message format:\n"
        "     [YouTube 새 영상]\n"
        "     {title}\n"
        "     {url}\n"
        "5) After sending, update state with newest ID.\n"
        "6) If nothing new, stay silent.\n"
        "7) Never send duplicate notifications."
    )


def build_cron_job(cfg: WatchConfig) -> dict:
    return {
        "name": cfg.job_name,
        "sessionTarget": "isolated",
        "enabled": True,
        "schedule": {"kind": "every", "everyMs": cfg.interval_min * 60_000},
        "payload": {
            "kind": "agentTurn",
            "message": build_agent_turn_message(cfg),
            "thinking": "low",
        },
        "delivery": {"mode": "none"},
    }


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"channels": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(cfg: WatchConfig) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_registry()

    channels = [c for c in registry.get("channels", []) if c.get("channel_id") != cfg.channel_id]
    channels.append(asdict(cfg))
    channels.sort(key=lambda x: x["channel_id"])

    REGISTRY_PATH.write_text(
        json.dumps({"channels": channels}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="YouTube watch cron payload generator")
    p.add_argument("--channel-id", required=True, help="YouTube channel id (UC...) ")
    p.add_argument("--target", required=True, help="Discord user id")
    p.add_argument("--interval-min", type=int, default=15, help="polling interval minutes")
    p.add_argument("--save", action="store_true", help="save to local registry file")
    p.add_argument("--message-only", action="store_true", help="print only payload.message")

    args = p.parse_args()

    cfg = WatchConfig(
        channel_id=args.channel_id.strip(),
        target=args.target.strip(),
        interval_min=max(1, int(args.interval_min)),
    )

    if args.save:
        save_registry(cfg)

    if args.message_only:
        print(build_agent_turn_message(cfg))
        return

    print(json.dumps(build_cron_job(cfg), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
