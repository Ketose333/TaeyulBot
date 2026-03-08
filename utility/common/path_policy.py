from __future__ import annotations

from pathlib import Path


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def ensure_not_under(path: Path, banned_root: Path, error: str) -> None:
    if is_under(path, banned_root):
        raise RuntimeError(error)


def resolve_out_dir(raw: str, default_dir: Path) -> Path:
    return Path((raw or '').strip() or str(default_dir)).expanduser().resolve()
