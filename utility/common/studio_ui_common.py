from __future__ import annotations

import json
import sys
from pathlib import Path


def ensure_workspace_imports(file_path: str) -> None:
    p = Path(file_path).resolve()
    studio_dir = p.parents[1]
    workspace_dir = p.parents[2]

    for candidate in (str(studio_dir), str(workspace_dir)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def load_publish_channel_options(workspace: Path, default_channel_id: str) -> list[tuple[str, str]]:
    file_path = workspace / 'studio' / 'publish_channels_allowlist.json'
    out: list[tuple[str, str]] = []

    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                for row in data:
                    if not isinstance(row, dict):
                        continue
                    cid = str(row.get('id', '')).strip()
                    label = str(row.get('label', '')).strip() or f'채널 {cid}'
                    if cid.isdigit():
                        out.append((cid, f'{label} ({cid})'))
            elif isinstance(data, dict):
                for cid, label in data.items():
                    cid = str(cid).strip()
                    if cid.isdigit():
                        name = str(label).strip() or f'채널 {cid}'
                        out.append((cid, f'{name} ({cid})'))
        except Exception:
            out = []

    dedup: dict[str, str] = {}
    for cid, label in out:
        dedup[cid] = label
    allowed = sorted(dedup.items(), key=lambda x: x[1].lower())

    default_opt = (default_channel_id, f'요청 채널 ({default_channel_id})')
    if not allowed:
        return [default_opt]
    if not any(cid == default_channel_id for cid, _ in allowed):
        return [default_opt] + allowed
    return allowed
