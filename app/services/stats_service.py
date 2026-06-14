from app.utils.date_utils import get_history


def get_sign_stats(sign: str, year: int, month: int, history: dict | None = None) -> dict:
    """history.json에서 해당 월의 별자리 순위 통계를 계산한다.

    history를 넘기면 디스크 재읽기를 생략한다(리더보드 일괄 집계용).
    """
    if history is None:
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

    return {
        "sign": sign,
        "year": year,
        "month": month,
        "total_days": len(daily),
        "start_day": daily[0][0],
        "end_day": daily[-1][0],
        "avg_rank": round(sum(ranks) / len(ranks), 1),
        "rank_1_count": ranks.count(1),
        "rank_12_count": ranks.count(12),
        "daily": daily,
    }


def get_leaderboard(user_signs: dict[int, str], year: int, month: int) -> list[dict]:
    """등록 유저별 이달 평균 순위를 집계해 오름차순 정렬한 리더보드."""
    history = get_history()
    board = []
    for user_id, sign in user_signs.items():
        stats = get_sign_stats(sign, year, month, history=history)
        if stats["total_days"] == 0:
            continue
        board.append({
            "user_id": user_id,
            "sign": sign,
            "avg_rank": stats["avg_rank"],
            "rank_1_count": stats["rank_1_count"],
            "total_days": stats["total_days"],
        })
    board.sort(key=lambda e: e["avg_rank"])
    return board
