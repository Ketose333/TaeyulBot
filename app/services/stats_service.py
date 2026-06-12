from datetime import date
import calendar

from app.utils.date_utils import get_history, kst_now


def get_sign_stats(sign: str, year: int, month: int) -> dict:
    """history.json에서 해당 월의 별자리 순위 통계를 계산한다."""
    history = get_history()

    prefix = f"{year:04d}-{month:02d}-"
    daily: list[tuple[str, int]] = []

    for date_str, entry in sorted(history.items()):
        if not date_str.startswith(prefix):
            continue
        rankings = entry.get("rankings", [])
        if sign in rankings:
            daily.append((date_str, rankings.index(sign) + 1))

    if not daily:
        return {
            "sign": sign,
            "year": year,
            "month": month,
            "total_days": 0,
            "avg_rank": None,
            "rank_1_count": 0,
            "rank_12_count": 0,
            "daily": [],
        }

    ranks = [r for _, r in daily]
    _, days_in_month = calendar.monthrange(year, month)

    return {
        "sign": sign,
        "year": year,
        "month": month,
        "total_days": len(daily),
        "days_in_month": days_in_month,
        "start_day": daily[0][0],
        "end_day": daily[-1][0],
        "avg_rank": round(sum(ranks) / len(ranks), 1),
        "rank_1_count": ranks.count(1),
        "rank_12_count": ranks.count(12),
        "daily": daily,
    }
