from __future__ import annotations

import sys
from pathlib import Path


def ensure_workspace_imports(file_path: str) -> None:
    p = Path(file_path).resolve()
    studio_dir = p.parents[1]
    workspace_dir = p.parents[2]

    for candidate in (str(studio_dir), str(workspace_dir)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
