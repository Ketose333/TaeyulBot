from datetime import date

from app.utils.saju_engine import (
    get_compatibility,
    get_daily_energy,
    get_daily_theme,
    get_zodiac_by_birthday,
    get_lucky_extras,
    parse_birthday,
    _josa,
    ZODIAC_SIGNS,
    ZODIAC_OHANG,
    LUCKY_COLORS,
    LUCKY_NUMBERS,
    LUCKY_DIRECTIONS,
)

import pytest


# ── 행운 요소 ─────────────────────────────────────────────────────────

def test_lucky_extras_deterministic():
    d = date(2026, 6, 12)
    a = get_lucky_extras("사자자리", d)
    b = get_lucky_extras("사자자리", d)
    assert a == b


def test_lucky_extras_values_from_ohang():
    d = date(2026, 6, 12)
    for sign in ZODIAC_SIGNS:
        ohang = ZODIAC_OHANG[sign]
        extras = get_lucky_extras(sign, d)
        assert extras["color"] in LUCKY_COLORS[ohang]
        assert extras["number"] in LUCKY_NUMBERS[ohang]
        assert extras["direction"] == LUCKY_DIRECTIONS[ohang]


# ── 궁합 ─────────────────────────────────────────────────────────────

def test_compatibility_symmetric():
    assert get_compatibility("양자리", "사자자리") == get_compatibility("사자자리", "양자리")


def test_compatibility_same_ohang_is_bihwa():
    # 양자리·사자자리 모두 화 → 비화
    result = get_compatibility("양자리", "사자자리")
    assert result["relation"] == "비화"
    assert 75 <= result["score"] <= 85


def test_compatibility_sangsaeng():
    # 화 → 토 (양자리=화, 황소자리=토), 상생
    result = get_compatibility("양자리", "황소자리")
    assert result["relation"] == "상생"
    assert 88 <= result["score"] <= 98


def test_compatibility_sanggeuk():
    # 수 → 화 (게자리=수, 양자리=화), 상극
    result = get_compatibility("게자리", "양자리")
    assert result["relation"] == "상극"
    assert 45 <= result["score"] <= 62


def test_compatibility_all_pairs_valid():
    for s1 in ZODIAC_SIGNS:
        for s2 in ZODIAC_SIGNS:
            r = get_compatibility(s1, s2)
            assert r["relation"] in ("상생", "비화", "상극", "중립")
            assert 45 <= r["score"] <= 98
            assert r["description"]


# ── 조사 ─────────────────────────────────────────────────────────────

def test_josa_for_five_elements():
    assert {ohang: _josa(ohang, "이/가") for ohang in "목화토금수"} == {
        "목": "이", "화": "가", "토": "가", "금": "이", "수": "가",
    }


def test_daily_energy_reuses_daily_theme():
    d = date(2026, 6, 12)

    assert get_daily_energy(d)["theme"] == get_daily_theme(d)


@pytest.mark.parametrize(
    ("month", "day", "sign"),
    [
        (1, 19, "염소자리"), (1, 20, "물병자리"),
        (2, 18, "물병자리"), (2, 19, "물고기자리"),
        (3, 20, "물고기자리"), (3, 21, "양자리"),
        (4, 19, "양자리"), (4, 20, "황소자리"),
        (5, 20, "황소자리"), (5, 21, "쌍둥이자리"),
        (6, 21, "쌍둥이자리"), (6, 22, "게자리"),
        (7, 22, "게자리"), (7, 23, "사자자리"),
        (8, 22, "사자자리"), (8, 23, "처녀자리"),
        (9, 22, "처녀자리"), (9, 23, "천칭자리"),
        (10, 22, "천칭자리"), (10, 23, "전갈자리"),
        (11, 22, "전갈자리"), (11, 23, "사수자리"),
        (12, 21, "사수자리"), (12, 22, "염소자리"),
    ],
)
def test_zodiac_by_birthday_boundaries(month, day, sign):
    assert get_zodiac_by_birthday(month, day) == sign


@pytest.mark.parametrize("value", ["6월 12일", "6/12", "6-12", "6.12"])
def test_parse_birthday_supported_formats(value):
    assert parse_birthday(value) == (6, 12)


@pytest.mark.parametrize("value", ["생일", "2/30", "13월 1일"])
def test_parse_birthday_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_birthday(value)
