import os
from app.utils.json_store import atomic_write_json, read_json
from app.utils.user_label import sanitize_display_label

ROOMS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rp_rooms.json")


def _load() -> dict:
    return read_json(ROOMS_PATH, {})


def _save(data: dict) -> None:
    atomic_write_json(ROOMS_PATH, data)


def _default_room() -> dict:
    return {"is_active": False, "opening": "", "turn_count": 0, "alias_by_user": {}}


def get_room(session_id: str) -> dict:
    data = _load()
    return data.get(str(session_id), _default_room())


def is_active(session_id: str) -> bool:
    return bool(get_room(session_id).get("is_active"))


def start_room(session_id: str, opening: str = "") -> None:
    data = _load()
    room = data.get(str(session_id), _default_room())
    room["is_active"] = True
    room["opening"] = (opening or "").strip()
    room["turn_count"] = 0
    data[str(session_id)] = room
    _save(data)


def end_room(session_id: str) -> None:
    data = _load()
    room = data.get(str(session_id))
    if room is None:
        return
    room["is_active"] = False
    room["turn_count"] = 0
    data[str(session_id)] = room
    _save(data)


def increment_turn(session_id: str) -> int:
    data = _load()
    room = data.get(str(session_id), _default_room())
    room["turn_count"] = int(room.get("turn_count", 0)) + 1
    data[str(session_id)] = room
    _save(data)
    return room["turn_count"]


def set_alias(session_id: str, user_id: str, alias: str) -> None:
    data = _load()
    room = data.get(str(session_id), _default_room())
    alias_by_user = room.get("alias_by_user") or {}
    alias = sanitize_display_label(alias)
    if alias:
        alias_by_user[str(user_id)] = alias
    else:
        alias_by_user.pop(str(user_id), None)
    room["alias_by_user"] = alias_by_user
    data[str(session_id)] = room
    _save(data)


def get_alias(session_id: str, user_id: str) -> str:
    room = get_room(session_id)
    return str((room.get("alias_by_user") or {}).get(str(user_id), ""))
