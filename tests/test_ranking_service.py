from datetime import date
import pytest

from app.services.ranking_service import generate_ranking, pick_theme_seed
from app.utils.saju_engine import ZODIAC_SIGNS


def test_ranking_returns_all_12_signs(today, sample_history):
    result = generate_ranking(today, sample_history)
    assert len(result) == 12
    assert set(result) == set(ZODIAC_SIGNS)


def test_ranking_is_deterministic_same_day(today, sample_history):
    r1 = generate_ranking(today, sample_history)
    r2 = generate_ranking(today, sample_history)
    assert r1 == r2


def test_ranking_differs_across_days(sample_history):
    d1 = date(2026, 6, 12)
    d2 = date(2026, 6, 13)
    r1 = generate_ranking(d1, sample_history)
    r2 = generate_ranking(d2, sample_history)
    assert r1 != r2, "날짜가 다르면 순위가 달라야 합니다"


def test_penalty_suppresses_recent_top(sample_history):
    # 2026-06-11 1위: 전갈자리 → 2026-06-12 페널티 적용
    today = date(2026, 6, 12)
    result = generate_ranking(today, sample_history)
    rank_of_jeonkal = result.index("전갈자리") + 1
    assert rank_of_jeonkal > 3, "최근 1위는 상위 3위에 포함되지 않아야 합니다"


def test_theme_seed_is_deterministic(today):
    s1 = pick_theme_seed(today)
    s2 = pick_theme_seed(today)
    assert s1 == s2


def test_theme_seed_differs_across_days():
    seeds = {pick_theme_seed(date(2026, 6, i)) for i in range(1, 15)}
    assert len(seeds) > 1, "날짜마다 테마 시드가 달라야 합니다"
