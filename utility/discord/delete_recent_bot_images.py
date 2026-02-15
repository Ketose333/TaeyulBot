#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os

import discord


async def run(args: argparse.Namespace) -> int:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("DISCORD_BOT_TOKEN이 필요함")
        return 2

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = False
    client = discord.Client(intents=intents)

    result = 0

    @client.event
    async def on_ready() -> None:
        nonlocal result
        try:
            ch = await client.fetch_channel(args.channel_id)
        except Exception as e:
            print(f"채널 조회 실패: {e}")
            result = 1
            await client.close()
            return

        targets: list[discord.Message] = []
        async for m in ch.history(limit=max(args.scan_limit, args.limit * 3), oldest_first=False):
            if m.author.id != args.author_id:
                continue
            if not m.attachments:
                continue
            has_image = any((a.content_type or "").startswith("image/") for a in m.attachments)
            if not has_image:
                continue
            targets.append(m)
            if len(targets) >= args.limit:
                break

        if args.verbose:
            print(f"삭제 대상 이미지 메시지: {len(targets)}")

        if args.execute:
            deleted = 0
            for m in targets:
                try:
                    await m.delete()
                    deleted += 1
                    await asyncio.sleep(0.25)
                except Exception:
                    continue
            if args.verbose:
                print(f"삭제 완료: {deleted}/{len(targets)}")

        await client.close()

    try:
        async with client:
            await client.start(token)
    except Exception as e:
        print(f"실행 실패: {e}")
        return 1

    return result


def main() -> int:
    p = argparse.ArgumentParser(description="최근 봇 이미지 메시지 N개 삭제")
    p.add_argument("--channel-id", type=int, required=True)
    p.add_argument("--author-id", type=int, required=True)
    p.add_argument("--limit", type=int, default=5, help="삭제할 이미지 메시지 개수")
    p.add_argument("--scan-limit", type=int, default=200, help="탐색할 최근 메시지 수")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
