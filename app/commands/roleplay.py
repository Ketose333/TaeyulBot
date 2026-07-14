from __future__ import annotations

import logging

import discord
from discord import app_commands

from app.utils import rp_store
from app.utils.discord_reply import build_discord_files, truncate_for_discord

log = logging.getLogger(__name__)

_DEFAULT_OPENING_TRIGGER = "새로운 RP 장면을 자연스럽게 시작해줘."


class RoleplayGroup(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(name="롤플레이", description="RP(롤플레이) 모드를 제어합니다.")

    @app_commands.command(name="시작", description="이 채널/DM에서 RP 모드를 시작합니다. 서버 채널이면 전용 스레드를 새로 만듭니다.")
    @app_commands.describe(주제="RP 오프닝 장면/주제 (선택)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def start(self, interaction: discord.Interaction, 주제: str = "") -> None:
        await interaction.response.defer(thinking=True)

        origin_channel = interaction.channel
        target_channel = origin_channel
        made_thread = False

        # 일반 텍스트 채널이면 RP 전용 스레드를 새로 만들어 원 채널과 분리한다
        # (DM/이미 스레드인 채널에서는 만들지 않고 그 자리에서 그대로 진행).
        if isinstance(origin_channel, discord.TextChannel):
            thread_name = (주제.strip()[:80] if 주제.strip() else "RP")
            try:
                target_channel = await origin_channel.create_thread(
                    name=thread_name, type=discord.ChannelType.public_thread
                )
                made_thread = True
            except Exception:
                log.exception("RP 스레드 생성 실패, 원 채널에서 진행")
                target_channel = origin_channel

        session_id = str(target_channel.id)
        rp_store.start_room(session_id, opening=주제)

        try:
            from app.services.llm_service import LLMService

            client = interaction.client
            if not hasattr(client, "llm_service"):
                client.llm_service = LLMService()

            trigger = 주제.strip() or _DEFAULT_OPENING_TRIGGER
            ai_reply, attachments = await client.llm_service.generate_response(
                session_id, trigger, author_id=interaction.user.id, author_name=interaction.user.display_name
            )
            ai_reply = truncate_for_discord(ai_reply)
            files = build_discord_files(attachments) if attachments else []
            await target_channel.send(content=ai_reply, files=files)
        except Exception:
            log.exception("RP 오프닝 생성 실패")
            await target_channel.send("RP 시작했어. 이제 그냥 채팅하면 돼.")

        if made_thread:
            await interaction.followup.send(f"RP 시작했어. {target_channel.mention}에서 이어갈게.")
        else:
            await interaction.followup.send("RP 시작했어.")

    @app_commands.command(name="끝", description="이 채널/DM에서 RP 모드를 종료합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def end(self, interaction: discord.Interaction) -> None:
        session_id = str(interaction.channel.id)
        rp_store.end_room(session_id)
        await interaction.response.send_message("RP 종료했어.")

        # RP 전용으로 만들어졌던 스레드라면 대화 종료 후 아카이브해 목록을 정리한다.
        if isinstance(interaction.channel, discord.Thread):
            try:
                await interaction.channel.edit(archived=True, locked=True)
            except Exception:
                log.exception("RP 스레드 아카이브 실패")

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
