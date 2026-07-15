from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.config import GROQ_API_KEY
from app.utils.generation_defaults import (
    DEFAULT_MUSIC_COUNTRY,
    DEFAULT_MUSIC_RECOMMEND_COUNT,
    MUSIC_MOOD_TAGS,
)
from app.utils.music_recommend import analyze_mood, recommend_real_tracks

log = logging.getLogger(__name__)

EMBED_COLOR = 0x1DB954  # Spotify green


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="음악추천", description="기분/상황에 맞는 실제 발매곡을 추천합니다.")
    @app_commands.describe(
        상황="지금 기분이나 원하는 분위기 (예: 우울해, 신나는 노래)",
        한국곡만="한국 가수 곡만 추천 (기본값: 꺼짐)",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def recommend_music_command(
        self, interaction: discord.Interaction, 상황: str, 한국곡만: bool = False
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            mood_analysis = await asyncio.to_thread(
                analyze_mood, 상황, MUSIC_MOOD_TAGS, GROQ_API_KEY
            )
            tracks, _provider = await asyncio.to_thread(
                recommend_real_tracks,
                mood_analysis.mood,
                상황,
                mood_analysis.search_keywords,
                DEFAULT_MUSIC_RECOMMEND_COUNT,
                GROQ_API_KEY,
                DEFAULT_MUSIC_COUNTRY,
                "KR" if 한국곡만 else None,
            )
        except Exception:
            log.exception("음악 추천 실패: situation=%s", 상황)
            await interaction.followup.send("❌ 음악 추천 중 오류가 발생했습니다.")
            return

        if not tracks:
            await interaction.followup.send("❌ 어울리는 곡을 찾지 못했습니다.")
            return

        embed = discord.Embed(title=f"🎵 '{상황}'에 어울리는 곡", color=EMBED_COLOR)
        for track in tracks:
            links = " · ".join(f"[{name}]({url})" for name, url in track.links.items())
            value = f"{track.reason}\n{links}" if track.reason else links
            embed.add_field(name=f"{track.title} - {track.artist}", value=value, inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
