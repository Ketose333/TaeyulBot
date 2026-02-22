#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List

import discord

BASE = Path('/home/user/.openclaw/workspace')
RUNTIME_DIR = BASE / 'studio' / 'dashboard' / 'runtime'
QUEUE_PATH = RUNTIME_DIR / 'discord_bulk_delete_queue.jsonl'
RUNS_PATH = RUNTIME_DIR / 'discord_bulk_delete_runs.jsonl'
LOCK_PATH = RUNTIME_DIR / 'discord_bulk_delete_runtime.lock'

BULK_DELETE_MAX_AGE_DAYS = 14


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')


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


async def detect_author_id(channel: discord.abc.Messageable, sample_limit: int = 100) -> int | None:
    latest_any: int | None = None
    latest_bot: int | None = None
    async for msg in channel.history(limit=sample_limit, oldest_first=False):
        if latest_any is None:
            latest_any = msg.author.id
        if getattr(msg.author, 'bot', False):
            latest_bot = msg.author.id
            break
    return latest_bot or latest_any


async def bulk_delete_messages(channel: discord.TextChannel | discord.Thread, messages: list[discord.Message]) -> int:
    deleted = 0
    for i in range(0, len(messages), 100):
        batch = messages[i:i + 100]
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
            continue
    return deleted


async def run_bulk_delete_job(job: dict[str, Any]) -> tuple[int, str, str]:
    token = os.getenv('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        return 2, '', 'DISCORD_BOT_TOKEN이 필요함'

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = False
    client = discord.Client(intents=intents)

    result_code = 0
    logs: list[str] = []

    @client.event
    async def on_ready() -> None:
        nonlocal result_code
        try:
            ch = await client.fetch_channel(int(job['channel_id']))
        except discord.HTTPException as e:
            logs.append(f'채널 조회 실패: {e}')
            result_code = 1
            await client.close()
            return

        if not isinstance(ch, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            logs.append(f'지원하지 않는 채널 타입: {type(ch).__name__}')
            result_code = 1
            await client.close()
            return

        author_id = job.get('author_id')
        if author_id is None and job.get('auto_author', True):
            author_id = await detect_author_id(ch, sample_limit=100)
            if job.get('verbose', True) and author_id is not None:
                logs.append(f'자동 감지 author-id: {author_id}')

        if author_id is None:
            logs.append('author-id 자동 감지 실패: --author-id 지정 필요')
            result_code = 2
            await client.close()
            return

        targets = await fetch_targets(
            channel=ch,
            author_id=int(author_id),
            limit=int(job.get('limit', 300)),
            after_message_id=job.get('after_message_id'),
            skip_pinned=bool(job.get('skip_pinned', True)),
        )

        if not targets:
            if job.get('verbose', True):
                logs.append('삭제 대상 없음')
            await client.close()
            return

        recent, old = split_by_age(targets)
        if job.get('verbose', True):
            logs.append(f"대상 {len(targets)}개 (bulk {len(recent)} / 개별 {len(old)})")

        if not job.get('execute', True):
            if job.get('verbose', True):
                logs.append('--execute 없음: 미리보기만 수행')
            await client.close()
            return

        deleted = 0
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            if recent:
                deleted += await bulk_delete_messages(ch, recent)
        else:
            old = old + recent

        if old:
            deleted += await delete_messages_one_by_one(old)

        if job.get('verbose', True):
            logs.append(f'삭제 완료: {deleted}/{len(targets)}')
        await client.close()

    try:
        async with client:
            await client.start(token)
    except discord.LoginFailure:
        return 2, '\n'.join(logs), '토큰 인증 실패'
    except Exception as e:
        return 1, '\n'.join(logs), f'실행 실패: {e}'

    return result_code, '\n'.join(logs), ''


def enqueue_job(
    channel_id: str,
    *,
    limit: int = 300,
    author_id: int | None = None,
    auto_author: bool = True,
    after_message_id: int | None = None,
    skip_pinned: bool = True,
    execute: bool = True,
    verbose: bool = True,
) -> str:
    _ensure_dirs()
    job_id = f'deld-{int(time.time())}-{uuid.uuid4().hex[:8]}'
    job = {
        'id': job_id,
        'created_at': now_iso(),
        'channel_id': str(channel_id),
        'limit': int(limit),
        'author_id': author_id,
        'auto_author': bool(auto_author),
        'after_message_id': after_message_id,
        'skip_pinned': bool(skip_pinned),
        'execute': bool(execute),
        'verbose': bool(verbose),
        'status': 'queued',
    }
    _append_jsonl(QUEUE_PATH, job)
    return job_id


def _pop_next_job() -> dict[str, Any] | None:
    _ensure_dirs()
    if not QUEUE_PATH.exists():
        return None
    lines = QUEUE_PATH.read_text(encoding='utf-8').splitlines()
    jobs = [ln for ln in lines if ln.strip()]
    if not jobs:
        return None
    first = jobs[0]
    QUEUE_PATH.write_text(('\n'.join(jobs[1:]) + ('\n' if len(jobs) > 1 else '')), encoding='utf-8')
    return json.loads(first)


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    started = now_iso()
    code, stdout, stderr = asyncio.run(run_bulk_delete_job(job))
    finished = now_iso()
    return {
        'id': job.get('id'),
        'type': 'discord-bulk-delete',
        'started_at': started,
        'finished_at': finished,
        'status': 'ok' if code == 0 else 'error',
        'code': code,
        'job': job,
        'stdout': (stdout or '').strip(),
        'stderr': (stderr or '').strip(),
    }


def _acquire_lock_or_exit() -> None:
    _ensure_dirs()
    if LOCK_PATH.exists():
        try:
            pid = int((LOCK_PATH.read_text(encoding='utf-8') or '0').strip() or '0')
            if pid > 0:
                os.kill(pid, 0)
                raise SystemExit(f'already running pid={pid}')
        except ProcessLookupError:
            pass
        except ValueError:
            pass
        except PermissionError:
            raise SystemExit('lock exists and cannot verify owner')
    LOCK_PATH.write_text(str(os.getpid()), encoding='utf-8')


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def runtime_loop(poll_sec: float = 2.0) -> int:
    _acquire_lock_or_exit()
    try:
        while True:
            job = _pop_next_job()
            if not job:
                time.sleep(max(0.5, poll_sec))
                continue
            result = _run_job(job)
            _append_jsonl(RUNS_PATH, result)
            print(f"[{result['finished_at']}] {result['id']} {result['status']} code={result['code']}")
    except KeyboardInterrupt:
        print('discord bulk delete runtime stopped')
        return 130
    finally:
        _release_lock()


def main() -> int:
    ap = argparse.ArgumentParser(description='Discord bulk-delete runtime / enqueue helper')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_run = sub.add_parser('run')
    p_run.add_argument('--poll-sec', type=float, default=float(os.getenv('DISCORD_BULK_DELETE_RUNTIME_POLL_SEC', '2')))

    p_q = sub.add_parser('enqueue')
    p_q.add_argument('--channel-id', required=True)
    p_q.add_argument('--limit', type=int, default=300)
    p_q.add_argument('--author-id', type=int, default=None)
    p_q.add_argument('--auto-author', action='store_true', default=True)
    p_q.add_argument('--no-auto-author', dest='auto_author', action='store_false')
    p_q.add_argument('--after-message-id', type=int, default=None)
    p_q.add_argument('--skip-pinned', action='store_true', default=True)
    p_q.add_argument('--no-skip-pinned', dest='skip_pinned', action='store_false')

    args = ap.parse_args()
    if args.cmd == 'run':
        return runtime_loop(poll_sec=args.poll_sec)

    job_id = enqueue_job(
        channel_id=args.channel_id,
        limit=args.limit,
        author_id=args.author_id,
        auto_author=args.auto_author,
        after_message_id=args.after_message_id,
        skip_pinned=args.skip_pinned,
    )
    print(json.dumps({'queued': True, 'job_id': job_id, 'queue': str(QUEUE_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
