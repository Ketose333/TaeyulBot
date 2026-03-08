from __future__ import annotations

from pathlib import Path

from utility.common.generation_defaults import WORKSPACE_ROOT

MEMORY_DIR = (WORKSPACE_ROOT / 'memory').resolve()

YOUTUBE_WATCH_STATE_PREFIX = 'youtube-watch-'
YOUTUBE_WATCH_STATE_SUFFIX = '.json'

YOUTUBE_WATCH_LAST_RESULT = (MEMORY_DIR / '.youtube_watch_last_result.json').resolve()
YOUTUBE_WATCH_RUN_RESULT = (MEMORY_DIR / '.youtube_watch_run_result.json').resolve()


def channel_state_path(slug: str) -> Path:
    s = (slug or '').strip()
    return (MEMORY_DIR / f'{YOUTUBE_WATCH_STATE_PREFIX}{s}{YOUTUBE_WATCH_STATE_SUFFIX}').resolve()
