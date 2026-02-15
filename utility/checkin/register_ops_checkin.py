#!/usr/bin/env python3
"""운영 점검(자동체크 + 사용자 3문항) 정기 DM 크론 job 생성 유틸리티."""

from __future__ import annotations

import argparse
import json


def build_message(target: str) -> str:
    return f"""Send a Discord DM check-in to user id {target} with exactly this tone and structure:

태율 운영 점검(확장) 왔어.

[자동 점검 체크리스트]
- 유튜브 알림 중복/백로그 이상 여부
- 일괄삭제 author-id 불일치 가능성
- 머슴닷컴 보고 포맷(제목+post id) 준수 여부
- 주요 cron runs 이상 패턴 여부

[승세 확인 2문항]
1) 요즘 알림 피로 체감은 어때? (괜찮음/많음)
2) 지금 제일 큰 병목 1개만 말해줘.

Rules:
- channel: discord
- action: send
- target: {target}
- send once per scheduled run
- keep it short
"""


def build_job(target: str, cron_expr: str, tz: str) -> dict:
    return {
        "name": f"Taeyul ops check-in expanded - {target}",
        "sessionTarget": "isolated",
        "enabled": True,
        "schedule": {"kind": "cron", "expr": cron_expr, "tz": tz},
        "payload": {
            "kind": "agentTurn",
            "message": build_message(target),
            "thinking": "low",
        },
        "delivery": {"mode": "none"},
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Generate cron job JSON for expanded ops check-in")
    p.add_argument("--target", required=True, help="Discord user id")
    p.add_argument("--cron", default="0 12 * * *", help="cron expr (default: daily 12:00, KST)")
    p.add_argument("--tz", default="Asia/Seoul", help="timezone")
    args = p.parse_args()

    print(json.dumps(build_job(args.target.strip(), args.cron.strip(), args.tz.strip()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
