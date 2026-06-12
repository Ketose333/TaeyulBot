from __future__ import annotations

import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from app.services.horoscope_service import get_today_fortune, get_sign_fortune
from app.services.stats_service import get_sign_stats
from app.utils.saju_engine import ZODIAC_SIGNS, ZODIAC_EMOJI
from app.utils.stats_chart import generate_rank_chart
from app.utils.user_store import get_zodiac, set_zodiac
from app.utils.date_utils import kst_now

RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
EMBED_COLOR  = 0x9B59B6
ASSETS_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "assets")

# Persistent view를 위한 static custom_id 상수
_CID_FORTUNE_SELECT = "yh:fortune_select"
_CID_STATS_SELECT   = "yh:stats_select"
_CID_USER_SELECT    = "yh:user_select"
_CID_RANKING_SELECT = "yh:ranking_select"
_CID_STATS_BTN      = "yh:stats_btn"
_CID_PROFILE_BTN    = "yh:profile_btn"
_CID_JAL_1          = "yh:jal_1"
_CID_JAL_12         = "yh:jal_12"


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _jal_image_path(rank: int) -> str | None:
    if rank == 1:
        return os.path.join(ASSETS_DIR, "jalsalge.png")
    if rank == 12:
        return os.path.join(ASSETS_DIR, "jalgake.png")
    return None


def _build_fortune_embed(sign: str, data: dict) -> discord.Embed:
    today_str = kst_now().strftime("%Y년 %m월 %d일")
    emoji = ZODIAC_EMOJI.get(sign, "⭐")
    rank = data["rank"]
    medal_icon = RANK_MEDALS.get(rank, "")
    embed = discord.Embed(
        title=f"{emoji} {sign} 오늘의 운세",
        description=f"✨ *{data['theme']}*",
        color=EMBED_COLOR,
    )
    embed.add_field(name="오늘의 순위", value=f"{medal_icon} **{rank}위** / 12위".strip(), inline=True)
    embed.add_field(name="오늘의 운세", value=data["fortune"], inline=False)
    embed.add_field(name="🍀 행운", value=data["lucky_item"], inline=False)
    embed.set_footer(text=f"{today_str} · 매일 오전 7시 갱신")
    return embed


def _build_stats_embed(
    stats: dict,
    sign: str,
    user: discord.User | discord.Member | None = None,
) -> discord.Embed:
    emoji = ZODIAC_EMOJI.get(sign, "⭐")
    now = kst_now()
    embed = discord.Embed(
        title=f"{emoji} {sign}  {now.year}년 {now.month}월 통계",
        color=EMBED_COLOR,
    )
    if user:
        embed.set_author(name=f"{user.display_name}의 통계", icon_url=user.display_avatar.url)
    if stats["total_days"] == 0:
        embed.description = "이번 달 데이터가 아직 없습니다."
        return embed
    embed.add_field(
        name="기간",
        value=f"{stats['start_day']} ~ {stats['end_day']} (총 {stats['total_days']}일)",
        inline=False,
    )
    embed.add_field(name="평균 순위", value=f"**{stats['avg_rank']}위** ({stats['total_days']}일 기준)", inline=True)
    embed.add_field(name="1위", value=f"**{stats['rank_1_count']}회**", inline=True)
    embed.add_field(name="12위", value=f"**{stats['rank_12_count']}회**", inline=True)
    return embed


async def _send_stats(
    interaction: discord.Interaction,
    sign: str,
    user: discord.User | discord.Member | None = None,
    edit: bool = False,
) -> None:
    now = kst_now()
    stats = get_sign_stats(sign, now.year, now.month)
    embed = _build_stats_embed(stats, sign, user=user)
    view = StatsView(current_sign=sign)

    if stats["daily"]:
        chart_buf = generate_rank_chart(sign, stats["daily"])
        file = discord.File(chart_buf, filename="chart.png")
        embed.set_image(url="attachment://chart.png")
        if edit:
            await interaction.response.defer()
            await interaction.edit_original_response(embed=embed, view=view, attachments=[file])
        else:
            await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
    else:
        if edit:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ── Components (persistent custom_id 적용) ────────────────────────────────────

class SignFortuneSelect(discord.ui.Select):
    def __init__(self, current_sign: str | None = None):
        options = [
            discord.SelectOption(
                label=s,
                emoji=ZODIAC_EMOJI.get(s, "⭐"),
                default=(s == current_sign),
            )
            for s in ZODIAC_SIGNS
        ]
        super().__init__(
            custom_id=_CID_FORTUNE_SELECT,
            placeholder="다른 별자리 운세 보기",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sign = self.values[0]
        try:
            data = get_sign_fortune(sign)
        except Exception as e:
            await interaction.response.send_message(f"오류: {e}", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=_build_fortune_embed(sign, data),
            view=FortuneView(sign, data["rank"]),
        )


class SignStatsSelect(discord.ui.Select):
    def __init__(self, current_sign: str | None = None):
        options = [
            discord.SelectOption(
                label=s,
                emoji=ZODIAC_EMOJI.get(s, "⭐"),
                default=(s == current_sign),
            )
            for s in ZODIAC_SIGNS
        ]
        super().__init__(
            custom_id=_CID_STATS_SELECT,
            placeholder="다른 별자리 통계 보기",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await _send_stats(interaction, self.values[0], edit=True)
        except Exception as e:
            await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)


class OtherUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            custom_id=_CID_USER_SELECT,
            placeholder="다른 이용자의 통계 보기",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        target = self.values[0]
        sign = get_zodiac(target.id)
        if not sign:
            await interaction.response.send_message(
                f"**{target.display_name}**님은 별자리가 등록되어 있지 않습니다.",
                ephemeral=True,
            )
            return
        try:
            await _send_stats(interaction, sign, user=target, edit=True)
        except Exception as e:
            await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)


class RankingSignSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id=_CID_RANKING_SELECT,
            placeholder="별자리를 선택해 운세 자세히 보기",
            options=[
                discord.SelectOption(label=s, emoji=ZODIAC_EMOJI.get(s, "⭐"))
                for s in ZODIAC_SIGNS
            ],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sign = self.values[0]
        try:
            data = get_sign_fortune(sign)
        except Exception as e:
            await interaction.response.send_message(f"오류: {e}", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=_build_fortune_embed(sign, data),
            view=FortuneView(sign, data["rank"]),
            ephemeral=True,
        )


class StatsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="내 통계보기",
            style=discord.ButtonStyle.primary,
            custom_id=_CID_STATS_BTN,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            sign = get_zodiac(interaction.user.id)
            if not sign:
                await interaction.response.send_message(
                    "`/내별자리`로 별자리를 먼저 등록해주세요.", ephemeral=True
                )
                return
            await _send_stats(interaction, sign)
        except Exception as e:
            await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)


class ProfileButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="내 프로필 보기",
            style=discord.ButtonStyle.secondary,
            custom_id=_CID_PROFILE_BTN,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            sign = get_zodiac(interaction.user.id)
            if not sign:
                await interaction.response.send_message(
                    "`/내별자리`로 별자리를 먼저 등록해주세요.", ephemeral=True
                )
                return
            now = kst_now()
            stats = get_sign_stats(sign, now.year, now.month)
            emoji = ZODIAC_EMOJI.get(sign, "⭐")
            embed = discord.Embed(
                title=f"{interaction.user.display_name}의 프로필",
                color=EMBED_COLOR,
            )
            embed.add_field(name="별자리", value=f"{emoji} **{sign}**", inline=True)
            if stats["total_days"] > 0:
                embed.add_field(name="이달 평균 순위", value=f"**{stats['avg_rank']}위**", inline=True)
                embed.add_field(name="이달 1위", value=f"**{stats['rank_1_count']}회**", inline=True)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)


class JalButton(discord.ui.Button):
    def __init__(self, rank: int):
        super().__init__(
            label="잘살게" if rank == 1 else "잘가게",
            style=discord.ButtonStyle.success if rank == 1 else discord.ButtonStyle.danger,
            custom_id=_CID_JAL_1 if rank == 1 else _CID_JAL_12,
        )
        self.rank = rank

    async def callback(self, interaction: discord.Interaction) -> None:
        path = _jal_image_path(self.rank)
        if path and os.path.exists(path):
            await interaction.message.reply(file=discord.File(path), mention_author=False)
            await interaction.response.defer()
        else:
            await interaction.response.send_message(
                "이미지 파일이 없습니다. `assets/jalsalge.png` 또는 `assets/jalgake.png`를 추가해주세요.",
                ephemeral=True,
            )


# ── Views (timeout=None + persistent) ─────────────────────────────────────────

class StatsView(discord.ui.View):
    def __init__(self, current_sign: str | None = None):
        super().__init__(timeout=None)
        self.add_item(SignStatsSelect(current_sign=current_sign))
        self.add_item(OtherUserSelect())


class FortuneView(discord.ui.View):
    def __init__(self, sign: str | None = None, rank: int = 0):
        super().__init__(timeout=None)
        self.add_item(SignFortuneSelect(current_sign=sign))
        self.add_item(StatsButton())
        self.add_item(ProfileButton())
        if rank == 1:
            self.add_item(JalButton(1))
        elif rank == 12:
            self.add_item(JalButton(12))

    @classmethod
    def for_persistence(cls) -> FortuneView:
        """봇 재시작 시 add_view() 등록용 — 모든 custom_id 포함."""
        view = cls.__new__(cls)
        discord.ui.View.__init__(view, timeout=None)
        view.add_item(SignFortuneSelect())
        view.add_item(StatsButton())
        view.add_item(ProfileButton())
        view.add_item(JalButton(1))
        view.add_item(JalButton(12))
        return view


class RankingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RankingSignSelect())


# ── Cog ───────────────────────────────────────────────────────────────────────

class HoroscopeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="별자리순위", description="오늘의 12개 별자리 운세 순위를 보여줍니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def today_ranking(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            data = get_today_fortune()
        except Exception as e:
            await interaction.followup.send(f"운세를 불러오는 중 오류가 발생했습니다: {e}", ephemeral=True)
            return

        today_str = kst_now().strftime("%Y년 %m월 %d일")
        embed = discord.Embed(
            title=f"🔮 {today_str} 별자리 운세 순위",
            description=f"✨ *{data['theme']}*",
            color=EMBED_COLOR,
        )
        lines = []
        for i, sign in enumerate(data["rankings"]):
            rank = i + 1
            medal = RANK_MEDALS.get(rank, f"`{rank:2d}위`")
            emoji = ZODIAC_EMOJI.get(sign, "⭐")
            fortune = data["fortunes"].get(sign, "")
            lines.append(f"{medal} **{emoji} {sign}** — {fortune}")

        embed.add_field(name="", value="\n".join(lines), inline=False)
        embed.set_footer(text="아래에서 별자리를 선택하면 자세한 운세를 볼 수 있어요 ✨")
        await interaction.followup.send(embed=embed, view=RankingView())

    @app_commands.command(name="별자리운세", description="오늘의 별자리 운세를 알려줍니다. 별자리 미입력 시 등록된 별자리를 사용합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(별자리="운세를 확인할 별자리 (미입력 시 등록된 별자리 사용)")
    @app_commands.choices(
        별자리=[app_commands.Choice(name=s, value=s) for s in ZODIAC_SIGNS]
    )
    async def sign_fortune(self, interaction: discord.Interaction, 별자리: str | None = None) -> None:
        await interaction.response.defer(thinking=True)
        if 별자리 is None:
            별자리 = get_zodiac(interaction.user.id)
            if not 별자리:
                await interaction.followup.send(
                    "`/내별자리`로 별자리를 먼저 등록하거나, 별자리를 직접 선택해주세요.",
                    ephemeral=True,
                )
                return
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.followup.send("올바른 별자리를 선택해주세요.", ephemeral=True)
            return
        try:
            data = get_sign_fortune(별자리)
        except Exception as e:
            await interaction.followup.send(f"운세를 불러오는 중 오류가 발생했습니다: {e}", ephemeral=True)
            return

        await interaction.followup.send(
            embed=_build_fortune_embed(별자리, data),
            view=FortuneView(별자리, data["rank"]),
        )

    @app_commands.command(name="내별자리", description="나의 별자리를 등록합니다. 통계와 프로필에 사용됩니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(별자리="등록할 별자리를 선택하세요")
    @app_commands.choices(
        별자리=[app_commands.Choice(name=s, value=s) for s in ZODIAC_SIGNS]
    )
    async def set_my_sign(self, interaction: discord.Interaction, 별자리: str) -> None:
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.response.send_message("올바른 별자리를 선택해주세요.", ephemeral=True)
            return
        set_zodiac(interaction.user.id, 별자리)
        emoji = ZODIAC_EMOJI.get(별자리, "⭐")
        await interaction.response.send_message(
            f"{emoji} **{별자리}**(으)로 등록됐어요! 이제 운세 메시지에서 통계와 프로필을 확인할 수 있습니다.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HoroscopeCog(bot))
