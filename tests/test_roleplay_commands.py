import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.commands.roleplay import RoleplayGroup
from app.utils import rp_store


def _make_interaction(channel_id=555, user_id=111):
    return SimpleNamespace(
        channel=SimpleNamespace(id=channel_id),
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(send_message=AsyncMock()),
    )


def test_group_registers_expected_subcommands():
    group = RoleplayGroup()
    names = {cmd.name for cmd in group.commands}
    assert names == {"시작", "끝", "이름", "사용자명"}


def test_start_activates_room(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    group = RoleplayGroup()
    interaction = _make_interaction()

    asyncio.run(group.start.callback(group, interaction, "폐쇄된 연구소"))

    assert rp_store.is_active("555") is True
    interaction.response.send_message.assert_awaited_once()


def test_end_deactivates_room(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.start_room("555", opening="시작")
    group = RoleplayGroup()
    interaction = _make_interaction()

    asyncio.run(group.end.callback(group, interaction))

    assert rp_store.is_active("555") is False


def test_set_alias_then_show_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    group = RoleplayGroup()
    interaction = _make_interaction()

    asyncio.run(group.set_alias.callback(group, interaction, "선배"))
    assert rp_store.get_alias("555", 111) == "선배"
    interaction.response.send_message.assert_awaited_once_with("이제부터 '선배'라고 부를게.")

    interaction2 = _make_interaction()
    asyncio.run(group.show_alias.callback(group, interaction2))
    interaction2.response.send_message.assert_awaited_once_with("현재 호칭: 선배")


def test_set_alias_empty_clears_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.set_alias("555", 111, "선배")
    group = RoleplayGroup()
    interaction = _make_interaction()

    asyncio.run(group.set_alias.callback(group, interaction, ""))

    assert rp_store.get_alias("555", 111) == ""
    interaction.response.send_message.assert_awaited_once_with("호칭 설정을 해제했어.")
