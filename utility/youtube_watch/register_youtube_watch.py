#!/usr/bin/env python3
"""YouTube watch target spec generator (current multi-target runtime format).

목적:
- `youtube-watch-uploads-10m` 크론 payload의 Targets 블록에 넣을
  채널 매핑 라인을 표준 형식으로 생성한다.
- 단일 채널 크론을 추가 생성하지 않는다.
- RSS/DM 전용 구형 포맷을 사용하지 않는다.

예시:
  python3 utility/youtube_watch/register_youtube_watch.py \
    --slug olee \
    --channel-id UCGsT7X-FSwHQ4RLq-ZMATHQ \
    --notify-channel 1197928196893577447
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from utility.common.generation_defaults import WORKSPACE_ROOT
from utility.common.youtube_watch_paths import channel_state_path

STATE_DIR = WORKSPACE_ROOT / "utility" / "youtube_watch" / "state"
REGISTRY_PATH = STATE_DIR / "channels.json"


@dataclass
class TargetSpec:
    slug: str
    channel_id: str
    notify_channel: str = "1471931748194455807"

    @property
    def state_file(self) -> str:
        return str(channel_state_path(self.slug))

    @property
    def target_line(self) -> str:
        return (
            f"- {self.slug}: {self.channel_id} -> state `{self.state_file}` "
            f"-> notify `channel:{self.notify_channel}`"
        )


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"targets": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(spec: TargetSpec) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    reg = load_registry()
    targets = [t for t in reg.get("targets", []) if t.get("slug") != spec.slug]
    targets.append(asdict(spec))
    targets.sort(key=lambda x: x["slug"])
    REGISTRY_PATH.write_text(
        json.dumps({"targets": targets}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Generate/update YouTube watch target mapping line")
    p.add_argument("--slug", required=True, help="human-readable key (e.g., idntt, olee)")
    p.add_argument("--channel-id", required=True, help="YouTube channel id (UC...)")
    p.add_argument(
        "--notify-channel",
        default="1471931748194455807",
        help="Discord channel id for upload notifications",
    )
    p.add_argument("--save", action="store_true", help="save target to local registry")
    p.add_argument(
        "--json",
        action="store_true",
        help="print JSON instead of a single target line",
    )

    args = p.parse_args()
    spec = TargetSpec(
        slug=args.slug.strip(),
        channel_id=args.channel_id.strip(),
        notify_channel=args.notify_channel.strip(),
    )

    if args.save:
        save_registry(spec)

    if args.json:
        print(json.dumps(asdict(spec), ensure_ascii=False, indent=2))
    else:
        print(spec.target_line)


if __name__ == "__main__":
    main()
