from __future__ import annotations

import io
import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.config import ENABLE_IMAGE_GENERATION, GEMINI_API_KEY
from app.utils.filename_policy import slugify_name
from app.utils.gemini_image import ext_from_mime as image_ext_from_mime
from app.utils.gemini_image import generate_image_with_fallback
from app.utils.gemini_tts import generate_tts
from app.utils.media_tools import _short_error, load_avatar_bytes

log = logging.getLogger(__name__)


class MediaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="이미지생성", description="한태율 정체성을 유지한 이미지를 생성합니다.")
    @app_commands.describe(프롬프트="원하는 장면/포즈/의상 등 (예: 웃는 얼굴 클로즈업)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def generate_image_command(self, interaction: discord.Interaction, 프롬프트: str) -> None:
        if not ENABLE_IMAGE_GENERATION:
            await interaction.response.send_message(
                "❌ 현재 이미지 생성 기능은 비활성화 상태입니다(Gemini 무료 티어 쿼터 소진)."
            )
            return
        if not GEMINI_API_KEY:
            await interaction.response.send_message("❌ 이미지 생성을 사용할 수 없습니다(GEMINI_API_KEY 미설정).")
            return

        await interaction.response.defer(thinking=True)
        try:
            img_bytes, mime, _ = await generate_image_with_fallback(
                GEMINI_API_KEY, 프롬프트, ref_image_bytes=load_avatar_bytes()
            )
        except Exception as e:
            log.warning("이미지 생성 실패: %s", e)
            await interaction.followup.send(f"❌ 이미지 생성 실패: {_short_error(e)}")
            return

        filename = f"{slugify_name(프롬프트)[:60]}.{image_ext_from_mime(mime)}"
        try:
            await interaction.followup.send(file=discord.File(io.BytesIO(img_bytes), filename=filename))
        except discord.HTTPException:
            log.exception("이미지 첨부 전송 실패: prompt=%s", 프롬프트)
            await interaction.followup.send("❌ 이미지 생성은 됐지만 전송에 실패했습니다.")

    @app_commands.command(name="음성생성", description="텍스트를 한태율 목소리 음성 파일로 만듭니다.")
    @app_commands.describe(텍스트="음성으로 만들 텍스트")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def generate_voice_command(self, interaction: discord.Interaction, 텍스트: str) -> None:
        if not GEMINI_API_KEY:
            await interaction.response.send_message("❌ 음성 생성을 사용할 수 없습니다(GEMINI_API_KEY 미설정).")
            return

        await interaction.response.defer(thinking=True)
        try:
            audio_bytes, ext = await generate_tts(GEMINI_API_KEY, 텍스트)
        except Exception as e:
            log.warning("음성 생성 실패: %s", e)
            await interaction.followup.send(f"❌ 음성 생성 실패: {_short_error(e)}")
            return

        filename = f"{slugify_name(텍스트)[:60]}.{ext}"
        try:
            await interaction.followup.send(file=discord.File(io.BytesIO(audio_bytes), filename=filename))
        except discord.HTTPException:
            log.exception("음성 첨부 전송 실패: text=%s", 텍스트)
            await interaction.followup.send("❌ 음성 생성은 됐지만 전송에 실패했습니다.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MediaCog(bot))
