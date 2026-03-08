#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from utility.common.bootstrap import ensure_utility_imports
    ensure_utility_imports(__file__)
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv


def main() -> int:
    load_env_prefer_dotenv()
    token = os.getenv('AIVEN_API_TOKEN', '').strip()
    project = os.getenv('AIVEN_PROJECT', '').strip()
    service = os.getenv('AIVEN_SERVICE', '').strip()

    if not token or not project or not service:
        print(json.dumps({'state': 'UNKNOWN', 'error': 'missing env'}, ensure_ascii=False))
        return 2

    url = f'https://api.aiven.io/v1/project/{project}/service/{service}'
    headers = {'Authorization': f'aivenv1 {token}'}

    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        print(json.dumps({'state': 'UNKNOWN', 'error': f'request failed: {e}'}, ensure_ascii=False))
        return 1

    if r.status_code != 200:
        print(json.dumps({'state': 'UNKNOWN', 'error': f'api {r.status_code}'}, ensure_ascii=False))
        return 1

    data = r.json().get('service', {})
    state = data.get('state') or data.get('service_state') or 'UNKNOWN'
    dbname = data.get('service_uri_params', {}).get('dbname') or ''
    print(json.dumps({'project': project, 'service': service, 'state': state, 'dbname': dbname}, ensure_ascii=False))
    return 0 if str(state).upper() in {'RUNNING', 'REBALANCING'} else 3


if __name__ == '__main__':
    raise SystemExit(main())
