#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import discord


async def run(channel_id: int, file_path: str, content: str) -> int:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("DISCORD_BOT_TOKEN이 필요함")
        return 2

    p = Path(file_path)
    if not p.exists() or not p.is_file():
        print(f"파일 없음: {p}")
        return 2

    intents = discord.Intents.default()
    intents.guilds = True

    client = discord.Client(intents=intents)
    code = 0

    @client.event
    async def on_ready() -> None:
        nonlocal code
        try:
            ch = await client.fetch_channel(channel_id)
            if not isinstance(ch, (discord.TextChannel, discord.Thread, discord.DMChannel)):
                print(f"지원하지 않는 채널 타입: {type(ch).__name__}")
                code = 1
            else:
                await ch.send(content=content or None, file=discord.File(str(p)))
                print(f"업로드 완료: {channel_id} -> {p}")
        except Exception as e:
            print(f"업로드 실패: {e}")
            code = 1
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        print("디스코드 토큰 로그인 실패")
        return 2
    except Exception as e:
        print(f"클라이언트 실행 실패: {e}")
        return 1

    return code


def main() -> None:
    ap = argparse.ArgumentParser(description="Send local media file to Discord channel")
    ap.add_argument("--channel-id", type=int, required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--content", default="")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args.channel_id, args.file, args.content)))


if __name__ == "__main__":
    main()
