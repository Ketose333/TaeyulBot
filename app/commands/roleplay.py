from __future__ import annotations

import logging

import discord
from discord import app_commands

from app.utils import rp_store

log = logging.getLogger(__name__)


class RoleplayGroup(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(name="롤플레이", description="RP(롤플레이) 모드를 제어합니다.")

    @app_commands.command(name="시작", description="이 채널/DM에서 RP 모드를 시작합니다.")
    @app_commands.describe(주제="RP 오프닝 장면/주제 (선택)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def start(self, interaction: discord.Interaction, 주제: str = "") -> None:
        session_id = str(interaction.channel.id)
        rp_store.start_room(session_id, opening=주제)
        await interaction.response.send_message("RP 시작했어. 이제 그냥 채팅하면 돼.")

    @app_commands.command(name="끝", description="이 채널/DM에서 RP 모드를 종료합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def end(self, interaction: discord.Interaction) -> None:
        session_id = str(interaction.channel.id)
        rp_store.end_room(session_id)
        await interaction.response.send_message("RP 종료했어.")

    @app_commands.command(name="이름", description="RP 중 나를 부를 호칭을 설정합니다(비우면 해제).")
    @app_commands.describe(호칭="RP에서 나를 부를 호칭 (비우면 해제)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def set_alias(self, interaction: discord.Interaction, 호칭: str = "") -> None:
        session_id = str(interaction.channel.id)
        rp_store.set_alias(session_id, interaction.user.id, 호칭)
        if 호칭.strip():
            await interaction.response.send_message(f"이제부터 '{호칭.strip()}'라고 부를게.")
        else:
            await interaction.response.send_message("호칭 설정을 해제했어.")

    @app_commands.command(name="사용자명", description="RP 중 현재 설정된 내 호칭을 확인합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def show_alias(self, interaction: discord.Interaction) -> None:
        session_id = str(interaction.channel.id)
        alias = rp_store.get_alias(session_id, interaction.user.id)
        await interaction.response.send_message(f"현재 호칭: {alias}" if alias else "지정된 호칭이 없어.")
