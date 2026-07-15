from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.utils.emoji_engine import render_text_emoji
from app.utils.heart_engine import render_heart

log = logging.getLogger(__name__)


class EmojiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="이모지생성", description="텍스트를 디스코드 커스텀 이모지 스타일 PNG로 만들어줍니다.")
    @app_commands.describe(텍스트="이모지로 만들 텍스트 (예: 잘살게)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def generate_text_emoji(self, interaction: discord.Interaction, 텍스트: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            emoji_name, buf = await asyncio.to_thread(render_text_emoji, 텍스트)
        except Exception:
            log.exception("텍스트 이모지 생성 실패: text=%s", 텍스트)
            await interaction.followup.send("❌ 이모지 생성 중 오류가 발생했습니다.")
            return

        await interaction.followup.send(
            f"✅ `{emoji_name}`",
            file=discord.File(buf, filename=f"{emoji_name}.png"),
        )

    @app_commands.command(name="하트생성", description="지정한 hex 색상의 하트 이모지 PNG를 만들어줍니다.")
    @app_commands.describe(색상="hex 색상 코드 (예: #112233)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def generate_heart_emoji(self, interaction: discord.Interaction, 색상: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            buf = await asyncio.to_thread(render_heart, 색상)
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}")
            return
        except Exception:
            log.exception("하트 이모지 생성 실패: color=%s", 색상)
            await interaction.followup.send("❌ 이모지 생성 중 오류가 발생했습니다.")
            return

        name = 색상.lstrip("#").lower() + "_heart"
        await interaction.followup.send(
            f"✅ `{name}`",
            file=discord.File(buf, filename=f"{name}.png"),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiCog(bot))
