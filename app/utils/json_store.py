import json
import os
import tempfile
from typing import Any


def read_json(path: str, default: Any = None) -> Any:
    """JSON 파일을 읽어 반환한다. 파일이 없으면 default(기본 {})를 돌려준다."""
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: str, data: Any) -> None:
    """JSON을 같은 디렉터리의 임시 파일에 쓴 뒤 원자적으로 교체한다."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=f".{os.path.basename(path)}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
