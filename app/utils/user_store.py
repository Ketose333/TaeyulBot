import os

from app.utils.json_store import atomic_write_json, read_json

USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.json")


def _load() -> dict:
    return read_json(USERS_PATH, {})


def _save(data: dict) -> None:
    atomic_write_json(USERS_PATH, data)


def set_zodiac(user_id: int, sign: str) -> None:
    data = _load()
    data[str(user_id)] = {"zodiac": sign}
    _save(data)


def get_zodiac(user_id: int) -> str | None:
    data = _load()
    entry = data.get(str(user_id))
    return entry["zodiac"] if entry else None


def load_all() -> dict[str, dict]:
    """등록된 모든 유저 {str(user_id): {"zodiac": sign}}."""
    return _load()
