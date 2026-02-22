#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
WORKSPACE = Path('/home/user/.openclaw/workspace')
MEMORY_DIR = WORKSPACE / 'memory'

def _today_path() -> Path:
    now = datetime.now(KST)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR / f"{now:%Y-%m-%d}.md"


def append_daily(line: str) -> None:
    if not (line or '').strip():
        return
    p = _today_path()
    with p.open('a', encoding='utf-8') as f:
        f.write((line.rstrip() + '\n'))


def append_retro(task: str, result: str, risk: str, next_one: str) -> None:
    append_daily(f"- [자동 회고] {task} | 결과: {result} | 위험: {risk} | 다음: {next_one}")


def maybe_log_feedback(text: str) -> str:
    """Disabled by user request: no automatic praise/feedback scraping."""
    return 'none'
