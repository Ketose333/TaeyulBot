#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time

try:
    from utility.common.openclaw_runtime import extract_json_object, resolve_openclaw_bin
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    sys.path.append(str(_Path(__file__).resolve().parent.parent.parent.parent))
    from utility.common.bootstrap import ensure_utility_imports
    ensure_utility_imports(__file__)
    from utility.common.openclaw_runtime import extract_json_object, resolve_openclaw_bin

OPENCLAW_BIN = resolve_openclaw_bin()


def _extract_json(text: str) -> dict:
    return extract_json_object(text)


def _expected_every_label(every_ms: int) -> str:
    if every_ms % 3600000 == 0:
        return f"{every_ms // 3600000}h"
    if every_ms % 60000 == 0:
        return f"{every_ms // 60000}m"
    return f"{every_ms}ms"


def _declared_label(name: str) -> str | None:
    for pattern in (r"every-(\d+)([mh])$", r"-(\d+)([mh])$"):
        m = re.search(pattern, name)
        if m:
            return f"{m.group(1)}{m.group(2)}"
    return None


def main() -> int:
    cmd = [
        OPENCLAW_BIN,
        "gateway",
        "call",
        "cron.list",
        "--timeout",
        "120000",
        "--params",
        '{"includeDisabled":true}',
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    data = _extract_json(out)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []

    if not jobs:
        print("ERROR|크론 목록을 읽지 못했어.")
        return 0

    now_ms = int(time.time() * 1000)
    failures: list[str] = []
    mismatches: list[str] = []
    delayed: list[str] = []

    for job in jobs:
        if not bool(job.get("enabled", True)):
            continue
        name = str(job.get("name", "(no-name)"))
        schedule = job.get("schedule", {}) or {}
        state = job.get("state", {}) or {}
        last_status = str(state.get("lastStatus", "-")).lower()
        next_run_ms = state.get("nextRunAtMs")

        if schedule.get("kind") == "every":
            try:
                expected = _expected_every_label(int(schedule.get("everyMs") or 0))
            except Exception:
                expected = None
            declared = _declared_label(name)
            if expected and declared and expected != declared:
                mismatches.append(f"{name}={expected}")

        if last_status not in {"ok", "-"}:
            failures.append(f"{name}:{last_status}")
        elif isinstance(next_run_ms, (int, float)) and next_run_ms < now_ms - (5 * 60 * 1000):
            delayed.append(name)

    parts: list[str] = []
    if failures:
        parts.append(f"실패 {len(failures)}건 ({', '.join(failures[:2])})")
    if mismatches:
        parts.append(f"이름-주기 불일치 {len(mismatches)}건 ({', '.join(mismatches[:2])})")
    if delayed:
        parts.append(f"다음 실행 지연 {len(delayed)}건 ({', '.join(delayed[:2])})")

    if failures:
        print("ERROR|" + " / ".join(parts))
    elif mismatches or delayed:
        print("WARN|" + " / ".join(parts))
    else:
        enabled_count = sum(1 for job in jobs if bool(job.get("enabled", True)))
        print(f"OK|활성 크론 {enabled_count}개 정상")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
