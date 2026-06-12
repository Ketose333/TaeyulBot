from io import BytesIO
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.commands.horoscope import (
    _build_daily_energy_embed,
    _build_fortune_embed,
    _build_ranking_embed,
    _send_interaction_error,
    _send_stats,
    _zodiac_label,
)


KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 6, 12, 9, 0, tzinfo=KST)


def test_daily_embeds_share_date_and_refresh_footer():
    fortune = _build_fortune_embed(
        "사자자리",
        {
            "rank": 1,
            "rank_delta": 2,
            "theme": "병오일 — 열정과 빛의 기운",
            "fortune": "좋은 하루입니다.",
            "lucky_item": "햇빛을 받아보세요",
            "lucky_extras": {"color": "빨강", "number": 7, "direction": "남쪽"},
        },
        NOW,
    )
    ranking = _build_ranking_embed(
        {
            "rankings": ["사자자리"],
            "theme": "병오일 — 열정과 빛의 기운",
            "fortunes": {"사자자리": "좋은 하루입니다."},
        },
        [],
        NOW,
    )
    energy = _build_daily_energy_embed(
        {
            "gan": "병",
            "ji": "오",
            "day_ohang": "화",
            "desc": "열정과 빛의 기운",
            "blessed": ["황소자리"],
            "challenged": ["천칭자리"],
        },
        NOW,
    )

    common_footer = "2026년 06월 12일 · KST 기준 · 매일 갱신"
    assert fortune.footer.text == common_footer
    assert ranking.footer.text == common_footer
    assert energy.footer.text == common_footer


def test_zodiac_labels_use_consistent_spacing_and_emphasis():
    assert _zodiac_label("사자자리") == "♌ 사자자리"
    assert _zodiac_label("사자자리", bold=True) == "**♌ 사자자리**"


def test_daily_energy_uses_josa_and_standard_zodiac_labels():
    embed = _build_daily_energy_embed(
        {
            "gan": "계",
            "ji": "해",
            "day_ohang": "수",
            "desc": "직관과 깊이의 기운",
            "blessed": ["쌍둥이자리"],
            "challenged": ["사자자리"],
        },
        NOW,
    )

    assert embed.fields[0].name == "🌟 기운 받는 별자리 (수가 생하는 오행)"
    assert embed.fields[0].value == "♊ 쌍둥이자리"
    assert embed.fields[1].value == "♌ 사자자리"


@pytest.mark.asyncio
async def test_send_stats_defers_before_generating_chart():
    events = []
    response = SimpleNamespace(
        defer=AsyncMock(side_effect=lambda **kwargs: events.append("defer")),
    )
    interaction = SimpleNamespace(
        response=response,
        edit_original_response=AsyncMock(side_effect=lambda **kwargs: events.append("edit")),
    )
    stats = {
        "total_days": 1,
        "start_day": "2026-06-12",
        "end_day": "2026-06-12",
        "avg_rank": 3.0,
        "rank_1_count": 0,
        "rank_12_count": 0,
        "daily": [("2026-06-12", 3)],
    }

    async def fake_to_thread(*args):
        events.append("chart")
        return BytesIO(b"chart")

    with (
        patch("app.commands.horoscope.get_sign_stats", return_value=stats),
        patch("app.commands.horoscope.asyncio.to_thread", side_effect=fake_to_thread),
    ):
        await _send_stats(interaction, "사자자리")

    assert events == ["defer", "chart", "edit"]
    response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)


@pytest.mark.asyncio
async def test_interaction_error_does_not_expose_exception_details():
    response = SimpleNamespace(
        is_done=lambda: False,
        send_message=AsyncMock(),
    )
    interaction = SimpleNamespace(response=response)

    await _send_interaction_error(interaction)

    message = response.send_message.await_args.args[0]
    assert "오류" in message
    assert "Exception" not in message
