#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def load_env_prefer_dotenv(dotenv_path: str | None = None) -> None:
    """Load .env values and prefer them over existing shell env.

    - Finds workspace .env by default.
    - Keeps parsing intentionally simple (KEY=VALUE, # comments).
    """
    path = Path(dotenv_path) if dotenv_path else Path('/home/user/.openclaw/workspace/.env')
    if not path.exists():
        return

    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        # strip optional matching quotes
        if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
            v = v[1:-1]
        os.environ[k] = v
