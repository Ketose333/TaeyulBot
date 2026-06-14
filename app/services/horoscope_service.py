from datetime import date

from app.services.ranking_service import generate_ranking
from app.utils.saju_engine import generate_all_fortunes, get_daily_theme, get_lucky_item, get_lucky_extras
from app.utils.date_utils import get_history, save_today, get_rank_delta, kst_today

_cache: dict[str, dict] = {}


def _cache_result(key: str, result: dict) -> dict:
    """오늘 키 하나만 유지 — 날짜가 바뀌면 이전 캐시는 버린다(무한 증가 방지)."""
    _cache.clear()
    _cache[key] = result
    return result


def get_today_fortune(today: date | None = None) -> dict:
    today = today or kst_today()
    key = today.isoformat()

    if key in _cache:
        return _cache[key]

    history = get_history()

    if key in history:
        entry = history[key]
        fortunes = generate_all_fortunes(entry["rankings"], today)
        return _cache_result(
            key, {"rankings": entry["rankings"], "theme": entry["theme"], "fortunes": fortunes}
        )

    rankings = generate_ranking(today, history)
    theme = get_daily_theme(today)
    fortunes = generate_all_fortunes(rankings, today)

    save_today(today, rankings, theme)

    return _cache_result(key, {"rankings": rankings, "theme": theme, "fortunes": fortunes})


def get_sign_fortune(sign: str, today: date | None = None) -> dict:
    today = today or kst_today()
    data = get_today_fortune(today)
    rank = data["rankings"].index(sign) + 1 if sign in data["rankings"] else None
    lucky_item = get_lucky_item(sign, today)
    rank_delta = get_rank_delta(get_history(), sign, rank) if rank is not None else None
    return {
        "sign": sign,
        "rank": rank,
        "fortune": data["fortunes"].get(sign, "운세 정보를 불러올 수 없습니다."),
        "lucky_item": lucky_item,
        "lucky_extras": get_lucky_extras(sign, today),
        "rank_delta": rank_delta,
        "theme": data["theme"],
    }
