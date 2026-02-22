#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import discord


async def run(channel_id: int, text_path: str) -> tuple[int, str]:
    token = (os.getenv('DISCORD_BOT_TOKEN') or '').strip()
    if not token:
        return 2, 'DISCORD_BOT_TOKEN이 필요해.'

    content = Path(text_path).read_text(encoding='utf-8').strip()
    if not content:
        return 2, '고정메시지 내용 파일이 비어있어.'

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    client = discord.Client(intents=intents)

    result = {'code': 0, 'msg': 'ok'}

    @client.event
    async def on_ready() -> None:
        try:
            ch = await client.fetch_channel(channel_id)
            sent = await ch.send(content)
            await sent.pin(reason='studio dashboard pinned message')
            result['msg'] = f'고정 완료: messageId={sent.id}'
        except Exception as e:
            result['code'] = 1
            result['msg'] = f'실패: {e}'
        finally:
            await client.close()

    try:
        async with client:
            await client.start(token)
    except discord.LoginFailure:
        return 2, '디스코드 토큰 인증 실패'
    return result['code'], result['msg']


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--channel-id', required=True, type=int)
    ap.add_argument('--text-path', required=True)
    args = ap.parse_args()
    code, msg = asyncio.run(run(args.channel_id, args.text_path))
    print(msg)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
