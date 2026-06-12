from datetime import date
from unittest.mock import patch

from app.services.stats_service import get_leaderboard
import app.utils.date_utils as date_utils
from app.utils.date_utils import get_rank_delta, get_yesterday_rankings


MOCK_HISTORY = {
    "2026-06-01": {"rankings": ["사자자리", "양자리", "천칭자리", "게자리", "황소자리",
                                 "쌍둥이자리", "처녀자리", "전갈자리", "사수자리",
                                 "염소자리", "물병자리", "물고기자리"]},
    "2026-06-02": {"rankings": ["양자리", "사자자리", "천칭자리", "게자리", "황소자리",
                                 "쌍둥이자리", "처녀자리", "전갈자리", "사수자리",
                                 "염소자리", "물병자리", "물고기자리"]},
}


# ── 리더보드 ─────────────────────────────────────────────────────────

@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_leaderboard_sorted_by_avg_rank(mock_h):
    # 사자자리: 1,2위 → 평균 1.5 / 양자리: 2,1위 → 평균 1.5 / 천칭자리: 3,3위 → 평균 3.0
    board = get_leaderboard({1: "사자자리", 2: "천칭자리", 3: "양자리"}, 2026, 6)
    assert [e["sign"] for e in board][-1] == "천칭자리"  # 평균 순위 최하위가 마지막
    avgs = [e["avg_rank"] for e in board]
    assert avgs == sorted(avgs)


@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_leaderboard_excludes_no_data(mock_h):
    # 데이터 없는 달이면 제외
    board = get_leaderboard({1: "사자자리"}, 2026, 5)
    assert board == []


@patch("app.services.stats_service.get_history", return_value=MOCK_HISTORY)
def test_leaderboard_empty_input(mock_h):
    assert get_leaderboard({}, 2026, 6) == []


# ── 순위 변동 ────────────────────────────────────────────────────────

def test_rank_delta_up_down_same():
    # 오늘 = 2026-06-12 가정 → 어제 = 2026-06-11
    history = {
        "2026-06-11": {"rankings": ["양자리", "사자자리", "천칭자리"]},  # 사자=2위
    }
    with patch.object(date_utils, "kst_today", return_value=date(2026, 6, 12)):
        # 어제 2위 → 오늘 1위면 +1 (상승)
        assert get_rank_delta(history, "사자자리", 1) == 1
        # 어제 2위 → 오늘 2위면 0 (동일)
        assert get_rank_delta(history, "사자자리", 2) == 0
        # 어제 1위 → 오늘 3위면 -2 (하락)
        assert get_rank_delta(history, "양자리", 3) == -2


def test_rank_delta_no_yesterday():
    with patch.object(date_utils, "kst_today", return_value=date(2026, 6, 12)):
        assert get_rank_delta({}, "사자자리", 1) is None
        assert get_yesterday_rankings({}) == []
