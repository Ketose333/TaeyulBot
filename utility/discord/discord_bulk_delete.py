#!/usr/bin/env python3
"""
Discord 메시지 일괄삭제 유틸리티.

기본 동작
- 지정 채널에서 특정 작성자(author_id) 메시지를 최근순으로 수집
- 기준 메시지(after_message_id) 이후만 대상으로 필터링 가능
- 14일 이내 메시지는 bulk delete, 14일 초과는 개별 delete로 fallback

필수 환경변수
- DISCORD_BOT_TOKEN

예시
python3 utility/discord/discord_bulk_delete.py \
  --channel-id 123456789012345678 \
  --author-id 1146169746971451452 \
  --limit 500 \
  --execute
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
from typing import Iterable, List

import discord


BULK_DELETE_MAX_AGE_DAYS = 14


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def split_by_age(messages: Iterable[discord.Message]) -> tuple[List[discord.Message], List[discord.Message]]:
    threshold = utcnow() - dt.timedelta(days=BULK_DELETE_MAX_AGE_DAYS)
    recent: list[discord.Message] = []
    old: list[discord.Message] = []
    for m in messages:
        (recent if m.created_at >= threshold else old).append(m)
    return recent, old


async def fetch_targets(
    channel: discord.abc.Messageable,
    author_id: int,
    limit: int,
    after_message_id: int | None,
    skip_pinned: bool,
) -> list[discord.Message]:
    after_obj = discord.Object(id=after_message_id) if after_message_id else None

    out: list[discord.Message] = []
    async for msg in channel.history(limit=limit, after=after_obj, oldest_first=False):
        if msg.author.id != author_id:
            continue
        if skip_pinned and msg.pinned:
            continue
        out.append(msg)
    return out


async def bulk_delete_messages(channel: discord.TextChannel | discord.Thread, messages: list[discord.Message]) -> int:
    deleted = 0
    # Discord 권장 배치 크기 100
    for i in range(0, len(messages), 100):
        batch = messages[i : i + 100]
        if not batch:
            continue
        await channel.delete_messages(batch)
        deleted += len(batch)
    return deleted


async def delete_messages_one_by_one(messages: list[discord.Message]) -> int:
    deleted = 0
    for msg in messages:
        try:
            await msg.delete()
            deleted += 1
            await asyncio.sleep(0.35)
        except discord.HTTPException:
            # 개별 실패는 건너뛰고 계속 진행
            continue
    return deleted


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

    result_code = 0

    @client.event
    async def on_ready() -> None:
        nonlocal result_code
        try:
            ch = await client.fetch_channel(args.channel_id)
        except discord.HTTPException as e:
            print(f"채널 조회 실패: {e}")
            result_code = 1
            await client.close()
            return

        if not isinstance(ch, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            print(f"지원하지 않는 채널 타입: {type(ch).__name__}")
            result_code = 1
            await client.close()
            return

        targets = await fetch_targets(
            channel=ch,
            author_id=args.author_id,
            limit=args.limit,
            after_message_id=args.after_message_id,
            skip_pinned=args.skip_pinned,
        )

        if not targets:
            if args.verbose:
                print("삭제 대상 없음")
            await client.close()
            return

        recent, old = split_by_age(targets)
        if args.verbose:
            print(f"대상 {len(targets)}개 (bulk {len(recent)} / 개별 {len(old)})")

        if not args.execute:
            if args.verbose:
                print("--execute 없음: 미리보기만 수행")
            await client.close()
            return

        deleted = 0

        # DMChannel에는 delete_messages(batch)가 없어서 개별 삭제로 처리
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            if recent:
                deleted += await bulk_delete_messages(ch, recent)
        else:
            old = old + recent
            recent = []

        if old:
            deleted += await delete_messages_one_by_one(old)

        if args.verbose:
            print(f"삭제 완료: {deleted}/{len(targets)}")
        await client.close()

    try:
        async with client:
            await client.start(token)
    except discord.LoginFailure:
        print("토큰 인증 실패")
        return 2
    except Exception as e:
        print(f"실행 실패: {e}")
        return 1

    return result_code


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discord 메시지 일괄삭제")
    p.add_argument("--channel-id", type=int, required=True, help="대상 채널 ID")
    p.add_argument("--author-id", type=int, required=True, help="삭제할 작성자 ID")
    p.add_argument("--limit", type=int, default=1000, help="탐색 메시지 최대 개수")
    p.add_argument("--after-message-id", type=int, default=None, help="이 메시지 이후만 삭제")
    p.add_argument("--execute", action="store_true", help="실제 삭제 실행")
    p.add_argument("--skip-pinned", action="store_true", default=True, help="고정 메시지는 삭제 대상에서 제외")
    p.add_argument("--include-pinned", action="store_false", dest="skip_pinned", help="고정 메시지도 삭제 대상에 포함")
    p.add_argument("--verbose", action="store_true", help="진행/완료 로그 출력 (기본: 무출력)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
