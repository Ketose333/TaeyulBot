from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.services.horoscope_service import get_today_fortune, get_sign_fortune
from app.services.stats_service import get_leaderboard
from app.utils.saju_engine import ZODIAC_SIGNS, get_compatibility, get_daily_energy
from app.utils.user_store import get_zodiac, set_zodiac, load_all
from app.utils.date_utils import kst_now, get_history, get_yesterday_rankings
from app.utils.discord_reply import send_interaction_error

from app.commands.horoscope_embeds import (
    _build_compatibility_embed,
    _build_compatibility_invite_embed,
    _build_daily_energy_embed,
    _build_fortune_embed,
    _build_leaderboard_embed,
    _build_profile_embed,
    _build_ranking_embed,
    _build_stats_embed,
    _registered_sign_message,
    _zodiac_label,
    _zodiac_select_options,
)
from app.commands.horoscope_ui import (
    CompatibilityInviteView,
    FortuneView,
    RankingView,
    StatsView,
    _compatibility_request_content,
    _compatibility_request_ids,
    _complete_compatibility_request,
    _get_registered_sign_or_reply,
    _send_stats,
    _sign_from_birthday,
    _unregistered_user_message,
)

INVALID_SIGN_MESSAGE = "올바른 별자리를 선택해주세요."
log = logging.getLogger(__name__)
ZODIAC_CHOICES = [app_commands.Choice(name=sign, value=sign) for sign in ZODIAC_SIGNS]


# ── Cog ───────────────────────────────────────────────────────────────────────

class HoroscopeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        original = getattr(error, "original", error)
        log.error(
            "슬래시 커맨드 처리 실패: command=%s user_id=%s",
            interaction.command.qualified_name if interaction.command else "unknown",
            interaction.user.id,
            exc_info=(type(original), original, original.__traceback__),
        )
        await send_interaction_error(interaction)

    @app_commands.command(name="운세순위", description="오늘의 12개 별자리 운세 순위를 보여줍니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def today_ranking(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            data = get_today_fortune()
        except Exception:
            log.exception("오늘의 별자리 순위 처리 실패")
            await send_interaction_error(interaction, "운세를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
            return

        now = kst_now()
        yesterday = get_yesterday_rankings(get_history())
        await interaction.followup.send(
            embed=_build_ranking_embed(data, yesterday, now),
            view=RankingView(),
        )

    @app_commands.command(name="운세", description="오늘의 별자리 운세를 알려줍니다. 별자리 미입력 시 등록된 별자리를 사용합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(별자리="운세를 확인할 별자리 (미입력 시 등록된 별자리 사용)")
    @app_commands.choices(별자리=ZODIAC_CHOICES)
    async def sign_fortune(self, interaction: discord.Interaction, 별자리: str | None = None) -> None:
        await interaction.response.defer(thinking=True)
        if 별자리 is None:
            별자리 = get_zodiac(interaction.user.id)
            if not 별자리:
                await interaction.followup.send(
                    "`/별자리`로 별자리를 먼저 등록하거나, 별자리를 직접 선택해주세요.",
                    ephemeral=True,
                )
                return
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.followup.send(INVALID_SIGN_MESSAGE, ephemeral=True)
            return
        try:
            data = get_sign_fortune(별자리)
        except Exception:
            log.exception("별자리 운세 커맨드 처리 실패: sign=%s", 별자리)
            await send_interaction_error(interaction, "운세를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
            return

        await interaction.followup.send(
            embed=_build_fortune_embed(별자리, data),
            view=FortuneView(별자리, data["rank"]),
        )

    @app_commands.command(name="운세통계", description="이달의 별자리 순위 통계를 보여줍니다. 별자리 미입력 시 등록된 별자리를 사용합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(별자리="통계를 확인할 별자리 (미입력 시 등록된 별자리 사용)")
    @app_commands.choices(별자리=ZODIAC_CHOICES)
    async def fortune_stats(self, interaction: discord.Interaction, 별자리: str | None = None) -> None:
        user: discord.User | discord.Member | None = None
        if 별자리 is None:
            별자리 = get_zodiac(interaction.user.id)
            if not 별자리:
                await interaction.response.send_message(
                    "`/별자리`로 별자리를 먼저 등록하거나, 별자리를 직접 선택해주세요.",
                    ephemeral=True,
                )
                return
            user = interaction.user
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.response.send_message(INVALID_SIGN_MESSAGE, ephemeral=True)
            return
        try:
            await _send_stats(interaction, 별자리, user=user)
        except Exception:
            log.exception("운세통계 커맨드 처리 실패: sign=%s", 별자리)
            await send_interaction_error(interaction)

    @app_commands.command(name="별자리", description="별자리 선택이나 생일 입력으로 나의 별자리를 등록합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        별자리="등록할 별자리를 선택하세요",
        생일="생일로 자동 계산 (예: 6월 12일 또는 6/12)",
    )
    @app_commands.choices(별자리=ZODIAC_CHOICES)
    async def set_my_sign(
        self,
        interaction: discord.Interaction,
        별자리: str | None = None,
        생일: str | None = None,
    ) -> None:
        if bool(별자리) == bool(생일):
            await interaction.response.send_message(
                "`별자리` 또는 `생일` 중 하나만 입력해주세요.",
                ephemeral=True,
            )
            return

        if 생일:
            try:
                별자리 = _sign_from_birthday(생일)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.response.send_message(INVALID_SIGN_MESSAGE, ephemeral=True)
            return
        set_zodiac(interaction.user.id, 별자리)
        await interaction.response.send_message(
            _registered_sign_message(별자리),
            ephemeral=True,
        )

    @app_commands.command(name="궁합", description="두 별자리의 오행 궁합을 봐드립니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        상대="궁합을 볼 상대 (등록된 별자리 사용)",
        별자리1="직접 지정할 첫 번째 별자리",
        별자리2="직접 지정할 두 번째 별자리",
    )
    @app_commands.choices(별자리1=ZODIAC_CHOICES, 별자리2=ZODIAC_CHOICES)
    async def compatibility(
        self,
        interaction: discord.Interaction,
        상대: discord.User | None = None,
        별자리1: str | None = None,
        별자리2: str | None = None,
    ) -> None:
        # 해석 우선순위: ① 상대 지정 → 양쪽 등록 별자리, ② 별자리1+2 직접 지정
        if 상대 is not None:
            sign1 = await _get_registered_sign_or_reply(interaction)
            if not sign1:
                return
            sign2 = get_zodiac(상대.id)
            if not sign2:
                if 상대.bot:
                    await interaction.response.send_message(
                        _unregistered_user_message(상대.display_name),
                        ephemeral=True,
                    )
                    return
                if interaction.guild is None:
                    await interaction.response.send_message(
                        "미등록 상대에게 궁합을 요청하려면 함께 있는 서버 채널에서 사용해주세요.",
                        ephemeral=True,
                    )
                    return
                await interaction.response.send_message(
                    content=_compatibility_request_content(interaction.user.id, 상대.id),
                    embed=_build_compatibility_invite_embed(상대.display_name),
                    view=CompatibilityInviteView(),
                    allowed_mentions=discord.AllowedMentions(
                        users=[상대],
                        roles=False,
                        everyone=False,
                        replied_user=False,
                    ),
                )
                return
            name1 = interaction.user.display_name
            name2 = f"{상대.display_name} 🤖" if 상대.id == interaction.client.user.id else 상대.display_name
        elif 별자리1 and 별자리2:
            sign1, sign2 = 별자리1, 별자리2
            name1 = name2 = None
        else:
            await interaction.response.send_message(
                "`상대`를 지정하거나, `별자리1`과 `별자리2`를 모두 선택해주세요.", ephemeral=True
            )
            return

        result = get_compatibility(sign1, sign2)
        await interaction.response.send_message(
            embed=_build_compatibility_embed(
                sign1,
                sign2,
                result,
                name1,
                name2,
                bot_match=상대 is not None and 상대.id == interaction.client.user.id,
            )
        )

    @app_commands.command(name="리더보드", description="이달 평균 순위가 가장 좋은 이용자들을 보여줍니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        all_users = load_all()
        if not all_users:
            await interaction.followup.send("아직 별자리를 등록한 이용자가 없습니다.", ephemeral=True)
            return

        # 길드면 해당 서버 멤버만, DM이면 전체 등록 유저 (폴백)
        guild = interaction.guild
        user_signs: dict[int, str] = {}
        for uid_str, entry in all_users.items():
            uid = int(uid_str)
            if guild is not None and guild.get_member(uid) is None:
                continue
            user_signs[uid] = entry["zodiac"]

        if not user_signs:
            await interaction.followup.send(
                "이 서버에 별자리를 등록한 이용자가 없습니다.", ephemeral=True
            )
            return

        now = kst_now()
        board = get_leaderboard(user_signs, now.year, now.month)
        if not board:
            await interaction.followup.send(
                "이달 집계할 순위 데이터가 아직 없습니다.", ephemeral=True
            )
            return

        scope = guild.name if guild is not None else "전체"
        people = {}
        for entry in board[:10]:
            person = (guild.get_member(entry["user_id"]) if guild is not None
                      else interaction.client.get_user(entry["user_id"]))
            if person:
                people[entry["user_id"]] = person.display_name
        await interaction.followup.send(embed=_build_leaderboard_embed(scope, board, people, now))


    @app_commands.command(name="오늘의기운", description="오늘의 천간·오행 기운과 별자리별 영향을 알려줍니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def daily_energy(self, interaction: discord.Interaction) -> None:
        today = kst_now()
        energy = get_daily_energy(today.date())
        await interaction.response.send_message(embed=_build_daily_energy_embed(energy, today))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HoroscopeCog(bot))
