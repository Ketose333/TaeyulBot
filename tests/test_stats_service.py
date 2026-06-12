from unittest.mock import patch
from app.services.stats_service import get_sign_stats

MOCK_HISTORY = {
    "2026-06-01": {"rankings": ["사자자리", "양자리", "천칭자리", "게자리", "황소자리",
                                 "쌍둥이자리", "처녀자리", "전갈자리", "사수자리",
                                 "염소자리", "물병자리", "물고기자리"]},
    "2026-06-02": {"rankings": ["천칭자리", "사자자리", "양자리", "게자리", "황소자리",
                                 "쌍둥이자리", "처녀자리", "전갈자리", "사수자리",
                                 "염소자리", "물병자리", "물고기자리"]},
    "2026-06-03": {"rankings": ["물고기자리", "천칭자리", "사자자리", "게자리", "황소자리",
                                 "쌍둥이자리", "처녀자리", "전갈자리", "사수자리",
                                 "염소자리", "물병자리", "양자리"]},
}


@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_stats_basic(mock_h):
    stats = get_sign_stats("사자자리", 2026, 6)
    assert stats["total_days"] == 3
    assert stats["rank_1_count"] == 1
    assert stats["rank_12_count"] == 0
    assert stats["avg_rank"] is not None


@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_stats_empty_month(mock_h):
    stats = get_sign_stats("사자자리", 2026, 5)
    assert stats["total_days"] == 0
    assert stats["avg_rank"] is None


@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_stats_daily_length(mock_h):
    stats = get_sign_stats("천칭자리", 2026, 6)
    assert len(stats["daily"]) == 3
