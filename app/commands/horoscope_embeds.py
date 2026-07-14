from __future__ import annotations

from datetime import datetime

import discord

from app.utils.date_utils import kst_now
from app.utils.saju_engine import ZODIAC_EMOJI, ZODIAC_SIGNS, _josa

RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
EMBED_COLOR = 0x9B59B6
DATE_FORMAT = "%Y년 %m월 %d일"
DAILY_FOOTER = "KST 기준 · 매일 갱신"
OHANG_EMOJI = {"목": "🌿", "화": "🔥", "토": "🪨", "금": "⚙️", "수": "💧"}


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


def _registered_sign_message(sign: str) -> str:
    return f"{_zodiac_label(sign, bold=True)}로 등록했어요!"


def _daily_footer_text(now: datetime | None = None) -> str:
    now = now or kst_now()
    return f"{now.strftime(DATE_FORMAT)} · {DAILY_FOOTER}"


def _daily_theme_text(theme: str) -> str:
    return f"✨ *{theme}*"


def _set_daily_footer(embed: discord.Embed, now: datetime | None = None) -> None:
    embed.set_footer(text=_daily_footer_text(now))


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


def _build_compatibility_invite_embed(target_name: str) -> discord.Embed:
    return _new_embed(
        "💌 궁합 요청",
        f"**{target_name}**님이 별자리를 등록하면 궁합을 바로 보여드려요.\n"
        "아래에서 별자리를 선택하거나 생일로 등록해주세요.",
    )


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
