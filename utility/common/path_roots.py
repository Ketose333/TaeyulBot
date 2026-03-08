from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
OPENCLAW_ROOT = WORKSPACE_ROOT.parent
MEDIA_ROOT = (OPENCLAW_ROOT / 'media').resolve()
