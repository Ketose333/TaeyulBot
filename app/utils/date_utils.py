import json
import os
from datetime import date, datetime, timedelta, timezone

from app.utils.json_store import atomic_write_json

KST = timezone(timedelta(hours=9))


def kst_today() -> date:
    return datetime.now(KST).date()


def kst_now() -> datetime:
    return datetime.now(KST)

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "history.json")
HISTORY_DAYS = 30


def _load_history() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return {}
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(history: dict) -> None:
    atomic_write_json(HISTORY_PATH, history)


def get_history() -> dict:
    return _load_history()


def save_today(today: date, rankings: list[str], theme: str) -> None:
    history = _load_history()
    history[today.isoformat()] = {
        "rankings": rankings,
        "theme": theme,
        "generated_at": f"{today.isoformat()}T00:00:00",
    }
    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    history = {k: v for k, v in history.items() if k > cutoff}
    _save_history(history)


def get_recent_top_signs(
    history: dict,
    days: int = 3,
    reference_date: date | None = None,
) -> list[str]:
    reference_date = reference_date or kst_today()
    result = []
    for i in range(1, days + 1):
        key = (reference_date - timedelta(days=i)).isoformat()
        if key in history and history[key]["rankings"]:
            result.append(history[key]["rankings"][0])
    return result


def get_yesterday_top3(history: dict) -> list[str]:
    yesterday = (kst_today() - timedelta(days=1)).isoformat()
    entry = history.get(yesterday)
    if not entry:
        return []
    return entry["rankings"][:3]


def get_yesterday_rankings(history: dict) -> list[str]:
    yesterday = (kst_today() - timedelta(days=1)).isoformat()
    entry = history.get(yesterday)
    if not entry:
        return []
    return entry.get("rankings", [])


def get_rank_delta(history: dict, sign: str, today_rank: int) -> int | None:
    """어제 순위 - 오늘 순위. 양수=상승, 음수=하락, 0=동일, 어제 없음=None."""
    yesterday = get_yesterday_rankings(history)
    if sign not in yesterday:
        return None
    return (yesterday.index(sign) + 1) - today_rank
