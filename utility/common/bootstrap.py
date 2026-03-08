from __future__ import annotations

import sys
from pathlib import Path


def ensure_utility_imports(file_path: str) -> None:
    p = Path(file_path).resolve()
    for parent in p.parents:
        if (parent / 'utility').exists():
            candidate = str(parent)
            if candidate not in sys.path:
                sys.path.append(candidate)
            return
