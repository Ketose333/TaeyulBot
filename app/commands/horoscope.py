from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from app.services.horoscope_service import get_today_fortune, get_sign_fortune
from app.services.stats_service import get_sign_stats, get_leaderboard
from app.utils.saju_engine import ZODIAC_SIGNS, ZODIAC_EMOJI, _josa, get_compatibility, get_daily_energy
from app.utils.stats_chart import generate_rank_chart
from app.utils.user_store import get_zodiac, set_zodiac, load_all
from app.utils.date_utils import kst_now, get_history, get_yesterday_rankings

RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
EMBED_COLOR  = 0x9B59B6
ASSETS_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
DATE_FORMAT  = "%Y년 %m월 %d일"
DAILY_FOOTER = "KST 기준 · 매일 갱신"
OHANG_EMOJI  = {"목": "🌿", "화": "🔥", "토": "🪨", "금": "⚙️", "수": "💧"}
INVALID_SIGN_MESSAGE = "올바른 별자리를 선택해주세요."
REGISTER_SIGN_MESSAGE = "`/내별자리`로 별자리를 먼저 등록해주세요."
log = logging.getLogger(__name__)
_CHART_LOCK = asyncio.Lock()
ZODIAC_CHOICES = [app_commands.Choice(name=sign, value=sign) for sign in ZODIAC_SIGNS]

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


def _delta_label(delta: int | None) -> str:
    """어제 대비 순위 변동을 ↑N/↓N/― 로 표기. 신규(None)는 빈 문자열."""
    if delta is None:
        return ""
    if delta > 0:
        return f"🔺{delta}"
    if delta < 0:
        return f"🔻{abs(delta)}"
    return "―"


def _zodiac_label(sign: str, *, bold: bool = False) -> str:
    label = f"{ZODIAC_EMOJI.get(sign, '⭐')} {sign}"
    return f"**{label}**" if bold else label


def _month_label(year: int, month: int) -> str:
    return f"{year}년 {month}월"


def _new_embed(title: str, description: str | None = None) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=EMBED_COLOR)


def _zodiac_select_options(current_sign: str | None = None) -> list[discord.SelectOption]:
    return [
        discord.SelectOption(
            label=sign,
            emoji=ZODIAC_EMOJI.get(sign, "⭐"),
            default=(sign == current_sign),
        )
        for sign in ZODIAC_SIGNS
    ]


def _unregistered_user_message(display_name: str) -> str:
    return f"**{display_name}**님은 별자리가 등록되어 있지 않습니다."


async def _get_registered_sign_or_reply(interaction: discord.Interaction) -> str | None:
    sign = get_zodiac(interaction.user.id)
    if sign:
        return sign
    await interaction.response.send_message(REGISTER_SIGN_MESSAGE, ephemeral=True)
    return None


def _daily_footer_text(now: datetime | None = None) -> str:
    now = now or kst_now()
    return f"{now.strftime(DATE_FORMAT)} · {DAILY_FOOTER}"


def _daily_theme_text(theme: str) -> str:
    return f"✨ *{theme}*"


def _set_daily_footer(embed: discord.Embed, now: datetime | None = None) -> None:
    embed.set_footer(text=_daily_footer_text(now))


async def _send_interaction_error(
    interaction: discord.Interaction,
    message: str = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def _build_fortune_embed(
    sign: str,
    data: dict,
    now: datetime | None = None,
) -> discord.Embed:
    rank = data["rank"]
    medal_icon = RANK_MEDALS.get(rank, "")
    embed = _new_embed(
        f"{_zodiac_label(sign)} 오늘의 운세",
        _daily_theme_text(data["theme"]),
    )

    delta_label = _delta_label(data.get("rank_delta"))
    rank_value = f"{medal_icon} **{rank}위** / 12위".strip()
    if delta_label:
        suffix = "어제와 동일" if delta_label == "―" else f"어제 대비 {delta_label}"
        rank_value += f"  ({suffix})"
    embed.add_field(name="오늘의 순위", value=rank_value, inline=False)

    embed.add_field(name="오늘의 운세", value=data["fortune"], inline=False)
    embed.add_field(name="🍀 행운", value=data["lucky_item"], inline=False)

    extras = data.get("lucky_extras")
    if extras:
        embed.add_field(name="🎨 행운의 색", value=extras["color"], inline=True)
        embed.add_field(name="🔢 행운의 숫자", value=str(extras["number"]), inline=True)
        embed.add_field(name="🧭 행운의 방향", value=extras["direction"], inline=True)

    _set_daily_footer(embed, now)
    return embed


def _build_ranking_embed(
    data: dict,
    yesterday: list[str],
    now: datetime | None = None,
) -> discord.Embed:
    now = now or kst_now()
    embed = _new_embed(
        f"🔮 {now.strftime(DATE_FORMAT)} 별자리 운세 순위",
        _daily_theme_text(data["theme"]),
    )
    lines = []
    for i, sign in enumerate(data["rankings"]):
        rank = i + 1
        medal = RANK_MEDALS.get(rank, f"{rank}위")
        fortune = data["fortunes"].get(sign, "")
        delta = (yesterday.index(sign) + 1) - rank if sign in yesterday else None
        label = _delta_label(delta)
        delta_str = f" `{label}`" if label else ""
        lines.append(f"{medal} {_zodiac_label(sign, bold=True)}{delta_str} — {fortune}")

    embed.add_field(name="", value="\n".join(lines), inline=False)
    _set_daily_footer(embed, now)
    return embed


def _build_daily_energy_embed(energy: dict, now: datetime | None = None) -> discord.Embed:
    now = now or kst_now()
    day_ohang = energy["day_ohang"]
    embed = _new_embed(
        f"{OHANG_EMOJI.get(day_ohang, '✨')} {now.strftime(DATE_FORMAT)} 오늘의 기운",
        _daily_theme_text(energy["theme"]),
    )

    if energy["blessed"]:
        embed.add_field(
            name=(f"🌟 기운 받는 별자리 ({day_ohang}"
                  f"{_josa(day_ohang, '이/가')} 생하는 오행)"),
            value="  ".join(_zodiac_label(sign) for sign in energy["blessed"]),
            inline=False,
        )
    if energy["challenged"]:
        embed.add_field(
            name=(f"⚡ 주의할 별자리 ({day_ohang}"
                  f"{_josa(day_ohang, '이/가')} 극하는 오행)"),
            value="  ".join(_zodiac_label(sign) for sign in energy["challenged"]),
            inline=False,
        )

    _set_daily_footer(embed, now)
    return embed


def _build_stats_embed(
    stats: dict,
    sign: str,
    user: discord.User | discord.Member | None = None,
    now: datetime | None = None,
) -> discord.Embed:
    now = now or kst_now()
    embed = _new_embed(f"{_zodiac_label(sign)} · {_month_label(now.year, now.month)} 통계")
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


def _build_profile_embed(
    user: discord.User | discord.Member,
    sign: str,
    stats: dict,
) -> discord.Embed:
    embed = _new_embed(f"{user.display_name}의 프로필")
    embed.add_field(name="별자리", value=_zodiac_label(sign, bold=True), inline=True)
    if stats["total_days"] > 0:
        embed.add_field(name="이달 평균 순위", value=f"**{stats['avg_rank']}위**", inline=True)
        embed.add_field(name="이달 1위", value=f"**{stats['rank_1_count']}회**", inline=True)
        recent = stats["daily"][-7:]
        if recent:
            timeline = " → ".join(str(rank) for _, rank in recent) + "위"
            embed.add_field(name="최근 7일 순위", value=timeline, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


def _build_compatibility_embed(
    sign1: str,
    sign2: str,
    result: dict,
    name1: str | None = None,
    name2: str | None = None,
    bot_match: bool = False,
) -> discord.Embed:
    label1 = _zodiac_label(sign1) + (f" ({name1})" if name1 else "")
    label2 = _zodiac_label(sign2) + (f" ({name2})" if name2 else "")
    embed = _new_embed(
        f"{result['emoji']} 궁합 결과",
        f"**{label1}**  ×  **{label2}**",
    )
    embed.add_field(name="궁합 점수", value=f"**{result['score']}점** / 100", inline=True)
    embed.add_field(name="관계", value=f"**{result['relation']}**", inline=True)
    embed.add_field(name="풀이", value=result["description"], inline=False)
    if bot_match:
        embed.set_footer(text="🤖 한태율 (2026년 6월 12일생 · ♊ 쌍둥이자리)")
    return embed


def _build_leaderboard_embed(
    scope: str,
    board: list[dict],
    people: dict[int, str],
    now: datetime,
) -> discord.Embed:
    embed = _new_embed(
        f"🏆 {scope} 리더보드 — {_month_label(now.year, now.month)}",
        "이달 평균 순위가 좋은 순서입니다.",
    )
    lines = []
    for i, entry in enumerate(board[:10]):
        rank = i + 1
        medal = RANK_MEDALS.get(rank, f"`{rank}.`")
        name = people.get(entry["user_id"], f"이용자 {entry['user_id']}")
        lines.append(
            f"{medal} **{name}** · {_zodiac_label(entry['sign'])} · "
            f"평균 **{entry['avg_rank']}위** "
            f"(1위 {entry['rank_1_count']}회 · {entry['total_days']}일)"
        )
    embed.add_field(name="", value="\n".join(lines), inline=False)
    return embed


async def _send_stats(
    interaction: discord.Interaction,
    sign: str,
    user: discord.User | discord.Member | None = None,
    edit: bool = False,
) -> None:
    if edit:
        await interaction.response.defer()
    else:
        await interaction.response.defer(ephemeral=True, thinking=True)

    now = kst_now()
    stats = get_sign_stats(sign, now.year, now.month)
    embed = _build_stats_embed(stats, sign, user=user, now=now)
    view = StatsView(current_sign=sign)

    if stats["daily"]:
        async with _CHART_LOCK:
            chart_buf = await asyncio.to_thread(generate_rank_chart, sign, stats["daily"])
        file = discord.File(chart_buf, filename="chart.png")
        embed.set_image(url="attachment://chart.png")
        await interaction.edit_original_response(embed=embed, view=view, attachments=[file])
    else:
        await interaction.edit_original_response(embed=embed, view=view, attachments=[])


# ── Components (persistent custom_id 적용) ────────────────────────────────────

class SignFortuneSelect(discord.ui.Select):
    def __init__(self, current_sign: str | None = None):
        super().__init__(
            custom_id=_CID_FORTUNE_SELECT,
            placeholder="다른 별자리 운세 보기",
            options=_zodiac_select_options(current_sign),
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sign = self.values[0]
        try:
            data = get_sign_fortune(sign)
        except Exception:
            log.exception("별자리 운세 선택 처리 실패: sign=%s", sign)
            await _send_interaction_error(interaction)
            return
        await interaction.response.edit_message(
            embed=_build_fortune_embed(sign, data),
            view=FortuneView(sign, data["rank"]),
        )


class SignStatsSelect(discord.ui.Select):
    def __init__(self, current_sign: str | None = None):
        super().__init__(
            custom_id=_CID_STATS_SELECT,
            placeholder="다른 별자리 통계 보기",
            options=_zodiac_select_options(current_sign),
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await _send_stats(interaction, self.values[0], edit=True)
        except Exception:
            log.exception("별자리 통계 선택 처리 실패: sign=%s", self.values[0])
            await _send_interaction_error(interaction)


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
        is_bot = target.id == interaction.client.user.id
        sign = get_zodiac(target.id)
        if not sign:
            await interaction.response.send_message(
                _unregistered_user_message(target.display_name),
                ephemeral=True,
            )
            return
        try:
            await _send_stats(interaction, sign, user=target, edit=True)
            if is_bot:
                await interaction.followup.send(
                    "🤖 *저 한태율예요! 6월 12일생 ♊ 쌍둥이자리입니다.*", ephemeral=True
                )
        except Exception:
            log.exception("다른 이용자 통계 처리 실패: user_id=%s", target.id)
            await _send_interaction_error(interaction)


class RankingSignSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id=_CID_RANKING_SELECT,
            placeholder="별자리를 선택해 운세 자세히 보기",
            options=_zodiac_select_options(),
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sign = self.values[0]
        try:
            data = get_sign_fortune(sign)
        except Exception:
            log.exception("순위에서 별자리 운세 처리 실패: sign=%s", sign)
            await _send_interaction_error(interaction)
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
            sign = await _get_registered_sign_or_reply(interaction)
            if not sign:
                return
            await _send_stats(interaction, sign)
        except Exception:
            log.exception("내 통계 처리 실패: user_id=%s", interaction.user.id)
            await _send_interaction_error(interaction)


class ProfileButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="내 프로필 보기",
            style=discord.ButtonStyle.secondary,
            custom_id=_CID_PROFILE_BTN,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            sign = await _get_registered_sign_or_reply(interaction)
            if not sign:
                return
            now = kst_now()
            stats = get_sign_stats(sign, now.year, now.month)
            await interaction.response.send_message(
                embed=_build_profile_embed(interaction.user, sign, stats),
                ephemeral=True,
            )
        except Exception:
            log.exception("프로필 처리 실패: user_id=%s", interaction.user.id)
            await _send_interaction_error(interaction)


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
        await _send_interaction_error(interaction)

    @app_commands.command(name="별자리순위", description="오늘의 12개 별자리 운세 순위를 보여줍니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def today_ranking(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            data = get_today_fortune()
        except Exception:
            log.exception("오늘의 별자리 순위 처리 실패")
            await _send_interaction_error(interaction, "운세를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
            return

        now = kst_now()
        yesterday = get_yesterday_rankings(get_history())
        await interaction.followup.send(
            embed=_build_ranking_embed(data, yesterday, now),
            view=RankingView(),
        )

    @app_commands.command(name="별자리운세", description="오늘의 별자리 운세를 알려줍니다. 별자리 미입력 시 등록된 별자리를 사용합니다.")
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
                    "`/내별자리`로 별자리를 먼저 등록하거나, 별자리를 직접 선택해주세요.",
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
            await _send_interaction_error(interaction, "운세를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
            return

        await interaction.followup.send(
            embed=_build_fortune_embed(별자리, data),
            view=FortuneView(별자리, data["rank"]),
        )

    @app_commands.command(name="내별자리", description="나의 별자리를 등록합니다. 통계와 프로필에 사용됩니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(별자리="등록할 별자리를 선택하세요")
    @app_commands.choices(별자리=ZODIAC_CHOICES)
    async def set_my_sign(self, interaction: discord.Interaction, 별자리: str) -> None:
        if 별자리 not in ZODIAC_SIGNS:
            await interaction.response.send_message(INVALID_SIGN_MESSAGE, ephemeral=True)
            return
        set_zodiac(interaction.user.id, 별자리)
        await interaction.response.send_message(
            f"{_zodiac_label(별자리, bold=True)}로 등록됐어요! "
            "이제 운세 메시지에서 통계와 프로필을 확인할 수 있습니다.",
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
                await interaction.response.send_message(
                    _unregistered_user_message(상대.display_name), ephemeral=True
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
