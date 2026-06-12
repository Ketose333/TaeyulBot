import json
import os

USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.json")


def _load() -> dict:
    if not os.path.exists(USERS_PATH):
        return {}
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_zodiac(user_id: int, sign: str) -> None:
    data = _load()
    data[str(user_id)] = {"zodiac": sign}
    _save(data)


def get_zodiac(user_id: int) -> str | None:
    data = _load()
    entry = data.get(str(user_id))
    return entry["zodiac"] if entry else None
