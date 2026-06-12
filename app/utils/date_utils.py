import json
import os
from datetime import date, datetime, timedelta, timezone

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
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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


def get_recent_top_signs(history: dict, days: int = 3) -> list[str]:
    today = kst_today()
    result = []
    for i in range(1, days + 1):
        key = (today - timedelta(days=i)).isoformat()
        if key in history and history[key]["rankings"]:
            result.append(history[key]["rankings"][0])
    return result


def get_yesterday_top3(history: dict) -> list[str]:
    yesterday = (kst_today() - timedelta(days=1)).isoformat()
    entry = history.get(yesterday)
    if not entry:
        return []
    return entry["rankings"][:3]
