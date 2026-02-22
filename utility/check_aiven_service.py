#!/usr/bin/env python3
import json
import os
import sys

import requests

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    for _p in _Path(__file__).resolve().parents:
        if (_p / 'utility').exists():
            sys.path.append(str(_p))
            break
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv


def main() -> int:
    load_env_prefer_dotenv()
    token = os.getenv("AIVEN_API_TOKEN", "").strip()
    project = os.getenv("AIVEN_PROJECT", "").strip()
    service = os.getenv("AIVEN_SERVICE", "").strip()

    if not token or not project or not service:
        print("Missing required env: AIVEN_API_TOKEN, AIVEN_PROJECT, AIVEN_SERVICE", file=sys.stderr)
        return 2

    url = f"https://api.aiven.io/v1/project/{project}/service/{service}"
    headers = {"Authorization": f"aivenv1 {token}"}

    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    if r.status_code != 200:
        print(f"API error {r.status_code}: {r.text[:500]}", file=sys.stderr)
        return 1

    data = r.json().get("service", {})
    state = data.get("state") or data.get("service_state") or "UNKNOWN"
    dbname = data.get("service_uri_params", {}).get("dbname") or ""

    result = {
        "project": project,
        "service": service,
        "state": state,
        "dbname": dbname,
    }
    print(json.dumps(result, ensure_ascii=False))

    ok_states = {"RUNNING", "REBALANCING"}
    return 0 if str(state).upper() in ok_states else 3


if __name__ == "__main__":
    raise SystemExit(main())
