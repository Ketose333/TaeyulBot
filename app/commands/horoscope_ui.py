from __future__ import annotations

import asyncio
import logging
import os
import re

import discord

from app.commands.horoscope_embeds import (
    _build_compatibility_embed,
    _build_compatibility_invite_embed,
    _build_fortune_embed,
    _build_profile_embed,
    _build_stats_embed,
    _registered_sign_message,
    _zodiac_select_options,
)
from app.services.horoscope_service import get_sign_fortune
from app.services.stats_service import get_sign_stats
from app.utils.date_utils import kst_now
from app.utils.saju_engine import get_compatibility, get_zodiac_by_birthday, parse_birthday
from app.utils.stats_chart import generate_rank_chart
from app.utils.user_store import get_zodiac, set_zodiac

log = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
REGISTER_SIGN_MESSAGE = "`/별자리`로 별자리를 먼저 등록해주세요."
_CHART_LOCK = asyncio.Lock()

# Persistent view를 위한 static custom_id 상수
_CID_FORTUNE_SELECT = "yh:fortune_select"
_CID_STATS_SELECT   = "yh:stats_select"
_CID_USER_SELECT    = "yh:user_select"
_CID_RANKING_SELECT = "yh:ranking_select"
_CID_STATS_BTN      = "yh:stats_btn"
_CID_PROFILE_BTN    = "yh:profile_btn"
_CID_JAL_1          = "yh:jal_1"
_CID_JAL_12         = "yh:jal_12"
_CID_COMPAT_SIGN    = "yh:compat_sign"
_CID_COMPAT_BDAY    = "yh:compat_birthday"
_COMPAT_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _jal_image_path(rank: int) -> str | None:
    if rank == 1:
        return os.path.join(ASSETS_DIR, "jalsalge.png")
    if rank == 12:
        return os.path.join(ASSETS_DIR, "jalgage.png")
    return None


def _sign_from_birthday(value: str) -> str:
    month, day = parse_birthday(value)
    return get_zodiac_by_birthday(month, day)


def _compatibility_request_content(requester_id: int, target_id: int) -> str:
    return f"<@{target_id}>님, <@{requester_id}>님이 궁합을 요청했어요!"


def _compatibility_request_ids(message: discord.Message) -> tuple[int, int] | None:
    user_ids = [int(user_id) for user_id in _COMPAT_MENTION_PATTERN.findall(message.content)]
    if len(user_ids) < 2:
        return None
    target_id, requester_id = user_ids[:2]
    return requester_id, target_id


def _message_user_name(
    interaction: discord.Interaction,
    message: discord.Message,
    user_id: int,
) -> str:
    user = next((mentioned for mentioned in message.mentions if mentioned.id == user_id), None)
    if not user and interaction.guild:
        user = interaction.guild.get_member(user_id)
    if not user:
        user = interaction.client.get_user(user_id)
    return user.display_name if user else f"이용자 {user_id}"


def _unregistered_user_message(display_name: str) -> str:
    return f"**{display_name}**님은 별자리가 등록되어 있지 않습니다."


async def _get_registered_sign_or_reply(interaction: discord.Interaction) -> str | None:
    sign = get_zodiac(interaction.user.id)
    if sign:
        return sign
    await interaction.response.send_message(REGISTER_SIGN_MESSAGE, ephemeral=True)
    return None


async def _send_interaction_error(
    interaction: discord.Interaction,
    message: str = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def _complete_compatibility_request(
    interaction: discord.Interaction,
    sign: str,
    message: discord.Message | None = None,
) -> None:
    message = message or interaction.message
    request_ids = _compatibility_request_ids(message) if message else None
    if not message or not request_ids:
        await interaction.response.send_message(
            "궁합 요청 정보를 찾을 수 없습니다. `/궁합`으로 다시 요청해주세요.",
            ephemeral=True,
        )
        return

    requester_id, target_id = request_ids
    if interaction.user.id != target_id:
        await interaction.response.send_message(
            "궁합 요청을 받은 상대만 등록할 수 있어요.",
            ephemeral=True,
        )
        return

    requester_sign = get_zodiac(requester_id)
    if not requester_sign:
        await interaction.response.send_message(
            "요청자의 별자리 정보를 찾을 수 없습니다. `/궁합`으로 다시 요청해주세요.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    set_zodiac(target_id, sign)
    result = get_compatibility(requester_sign, sign)
    embed = _build_compatibility_embed(
        requester_sign,
        sign,
        result,
        _message_user_name(interaction, message, requester_id),
        interaction.user.display_name,
        bot_match=(
            requester_id == interaction.client.user.id
            or target_id == interaction.client.user.id
        ),
    )
    await message.edit(content=None, embed=embed, view=None)
    await interaction.followup.send(_registered_sign_message(sign), ephemeral=True)


async def _send_stats(
    interaction: discord.Interaction,
    sign: str,
    user: discord.User | discord.Member | None = None,
    edit: bool = False,
) -> None:
    if edit:
        await interaction.response.defer()
    else:
        await interaction.response.defer(thinking=True)

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
                    "🤖 *저 한태율이에요! 6월 12일생 ♊ 쌍둥이자리입니다.*", ephemeral=True
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
            await _send_stats(interaction, sign, user=interaction.user)
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


class CompatibilitySignSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id=_CID_COMPAT_SIGN,
            placeholder="내 별자리 선택하기",
            options=_zodiac_select_options(),
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await _complete_compatibility_request(interaction, self.values[0])
        except Exception:
            log.exception("궁합 요청 별자리 등록 실패: user_id=%s", interaction.user.id)
            await _send_interaction_error(interaction)


class BirthdayRegistrationModal(discord.ui.Modal):
    def __init__(self, message: discord.Message):
        super().__init__(title="생일로 별자리 등록")
        self.source_message = message
        self.birthday = discord.ui.TextInput(
            label="생일",
            placeholder="예: 6월 12일 또는 6/12",
            min_length=3,
            max_length=10,
        )
        self.add_item(self.birthday)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            sign = _sign_from_birthday(self.birthday.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        try:
            await _complete_compatibility_request(
                interaction,
                sign,
                message=self.source_message,
            )
        except Exception:
            log.exception("궁합 요청 생일 등록 실패: user_id=%s", interaction.user.id)
            await _send_interaction_error(interaction)


class CompatibilityBirthdayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="생일로 등록",
            style=discord.ButtonStyle.primary,
            custom_id=_CID_COMPAT_BDAY,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        message = interaction.message
        request_ids = _compatibility_request_ids(message) if message else None
        if not message or not request_ids:
            await interaction.response.send_message(
                "궁합 요청 정보를 찾을 수 없습니다. `/궁합`으로 다시 요청해주세요.",
                ephemeral=True,
            )
            return
        _, target_id = request_ids
        if interaction.user.id != target_id:
            await interaction.response.send_message(
                "궁합 요청을 받은 상대만 등록할 수 있어요.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(BirthdayRegistrationModal(message))


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
            await interaction.response.defer()
            await interaction.message.reply(file=discord.File(path), mention_author=False)
        else:
            await interaction.response.send_message(
                "이미지 파일이 없습니다. `assets/jalsalge.png` 또는 `assets/jalgage.png`를 추가해주세요.",
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


class CompatibilityInviteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CompatibilitySignSelect())
        self.add_item(CompatibilityBirthdayButton())
