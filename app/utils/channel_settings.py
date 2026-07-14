import os
from app.utils.json_store import atomic_write_json, read_json

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "channel_settings.json")
CHANNELS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "free_channels.json")

def get_channel_settings(channel_id: int) -> dict:
    data = read_json(SETTINGS_PATH, {})
    entry = data.get(str(channel_id), {})
    return {
        "temperature": entry.get("temperature", 0.7),
        "model": entry.get("model", "Gemini")
    }

def set_channel_setting(channel_id: int, key: str, value) -> None:
    data = read_json(SETTINGS_PATH, {})
    if str(channel_id) not in data:
        data[str(channel_id)] = {}
    data[str(channel_id)][key] = value
    atomic_write_json(SETTINGS_PATH, data)


def _load_free_channels() -> list:
    return read_json(CHANNELS_PATH, [])


def _save_free_channels(data: list) -> None:
    atomic_write_json(CHANNELS_PATH, data)


def enable_free_response(channel_id: int) -> None:
    data = _load_free_channels()
    if channel_id not in data:
        data.append(channel_id)
        _save_free_channels(data)


def disable_free_response(channel_id: int) -> None:
    data = _load_free_channels()
    if channel_id in data:
        data.remove(channel_id)
        _save_free_channels(data)


def is_free_response_enabled(channel_id: int) -> bool:
    data = _load_free_channels()
    return channel_id in data
