import json
from unittest.mock import patch

import pytest

from app.utils.json_store import atomic_write_json


def test_atomic_write_json_replaces_existing_file(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"old": true}', encoding="utf-8")

    atomic_write_json(str(path), {"새값": [1, 2, 3]})

    assert json.loads(path.read_text(encoding="utf-8")) == {"새값": [1, 2, 3]}
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_json_cleans_up_temp_file_on_replace_failure(tmp_path):
    path = tmp_path / "data.json"

    with patch("app.utils.json_store.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(OSError, match="replace failed"):
            atomic_write_json(str(path), {"value": 1})

    assert list(tmp_path.glob("*.tmp")) == []
