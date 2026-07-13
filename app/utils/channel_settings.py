import os
from app.utils.json_store import atomic_write_json, read_json

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "channel_settings.json")

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
