from __future__ import annotations

import os
import json
import shutil
from pathlib import Path


def resolve_openclaw_bin() -> str:
    candidates = [
        os.environ.get("OPENCLAW_BIN", "").strip(),
        str((Path.home() / ".npm-global" / "bin" / "openclaw").resolve()),
        shutil.which("openclaw") or "",
        "openclaw",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == "openclaw" or Path(candidate).exists():
            return candidate
    return "openclaw"


def extract_json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        return {}

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:idx + 1])
                except Exception:
                    return {}
    return {}
