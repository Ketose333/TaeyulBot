import os
import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class TaeyulBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # /리더보드에서 서버 멤버를 식별하기 위해 필요 (privileged — Developer Portal에서 토글)
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.load_extension("app.commands.horoscope")

        # 재시작 후에도 버튼·드랍다운이 살아있도록 persistent view 등록
        from app.commands.horoscope import FortuneView, StatsView, RankingView
        self.add_view(FortuneView.for_persistence())
        self.add_view(StatsView())
        self.add_view(RankingView())

        # 글로벌 동기화 — User-Installable App으로 모든 서버·DM에서 사용 가능
        await self.tree.sync()
        log.info("슬래시 커맨드 글로벌 동기화 완료 (전파까지 최대 1시간 소요)")

        # 개발 중 즉시 반영이 필요하면 GUILD_ID 설정
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("개발용 길드 즉시 동기화 완료 (GUILD_ID=%s)", guild_id)

    async def on_ready(self) -> None:
        await self.change_presence(activity=discord.Game(name="한태율 | /별자리순위"))
        log.info("봇 준비 완료: %s (ID: %s)", self.user, self.user.id)


def create_bot() -> TaeyulBot:
    return TaeyulBot()
