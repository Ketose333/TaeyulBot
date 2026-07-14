from app.utils import rp_store


def test_start_and_is_active(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))

    assert rp_store.is_active("chan1") is False
    rp_store.start_room("chan1", opening="폐쇄된 연구소")
    assert rp_store.is_active("chan1") is True
    room = rp_store.get_room("chan1")
    assert room["opening"] == "폐쇄된 연구소"
    assert room["turn_count"] == 0


def test_end_room(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))

    rp_store.start_room("chan1", opening="시작")
    rp_store.end_room("chan1")
    assert rp_store.is_active("chan1") is False


def test_end_room_missing_channel_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.end_room("never-started")  # 예외 없이 조용히 무시


def test_increment_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))

    rp_store.start_room("chan1")
    assert rp_store.increment_turn("chan1") == 1
    assert rp_store.increment_turn("chan1") == 2
    assert rp_store.get_room("chan1")["turn_count"] == 2


def test_set_and_get_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))

    rp_store.start_room("chan1")
    rp_store.set_alias("chan1", 111, "선배")
    assert rp_store.get_alias("chan1", 111) == "선배"
    assert rp_store.get_alias("chan1", 222) == ""


def test_set_alias_empty_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))

    rp_store.start_room("chan1")
    rp_store.set_alias("chan1", 111, "선배")
    rp_store.set_alias("chan1", 111, "")
    assert rp_store.get_alias("chan1", 111) == ""
