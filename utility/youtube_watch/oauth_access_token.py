#!/usr/bin/env python3
"""Google OAuth refresh_token -> access_token helper.

안전한 최소 유틸:
- .env 에 있는 GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN 사용
- access_token만 발급 확인(기본)
- --print-token 옵션을 주지 않으면 토큰 원문은 출력하지 않음
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def _load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def _get(name: str, dotenv: dict[str, str]) -> str:
    return (os.getenv(name) or dotenv.get(name) or "").strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Issue Google OAuth access token from refresh token")
    p.add_argument(
        "--env-file",
        default=str((Path('/home/user/.openclaw/workspace') / ' .env').resolve()),
        help="dotenv file path (default: workspace .env)",
    )
    p.add_argument("--print-token", action="store_true", help="print raw access token")
    args = p.parse_args()

    dotenv = _load_dotenv(Path(args.env_file))
    client_id = _get("GOOGLE_CLIENT_ID", dotenv)
    client_secret = _get("GOOGLE_CLIENT_SECRET", dotenv)
    refresh_token = _get("GOOGLE_REFRESH_TOKEN", dotenv)

    if not (client_id and client_secret and refresh_token):
        print("missing GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN", file=sys.stderr)
        return 2

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        detail = getattr(e, "read", lambda: b"")()
        msg = detail.decode("utf-8", errors="replace") if detail else str(e)
        print(f"token_exchange_failed: {msg[:400]}", file=sys.stderr)
        return 1

    access_token = payload.get("access_token", "")
    if not access_token:
        print(f"token_exchange_failed: {json.dumps(payload, ensure_ascii=False)[:400]}", file=sys.stderr)
        return 1

    if args.print_token:
        print(access_token)
    else:
        print(
            json.dumps(
                {
                    "ok": True,
                    "token_type": payload.get("token_type"),
                    "expires_in": payload.get("expires_in"),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
