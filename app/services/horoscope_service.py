from datetime import date

from app.services.ranking_service import generate_ranking, pick_theme_seed
from app.utils.saju_engine import generate_all_fortunes, get_daily_theme, get_lucky_item, get_lucky_extras, ZODIAC_SIGNS  # noqa: F401
from app.utils.date_utils import get_history, save_today, get_yesterday_top3, get_rank_delta, kst_today

_cache: dict[str, dict] = {}


def get_today_fortune(today: date | None = None) -> dict:
    today = today or kst_today()
    key = today.isoformat()

    if key in _cache:
        return _cache[key]

    history = get_history()

    if key in history:
        entry = history[key]
        fortunes = generate_all_fortunes(entry["rankings"], today)
        result = {"rankings": entry["rankings"], "theme": entry["theme"], "fortunes": fortunes}
        _cache[key] = result
        return result

    rankings = generate_ranking(today, history)
    theme = get_daily_theme(today)
    fortunes = generate_all_fortunes(rankings, today)

    save_today(today, rankings, theme)

    result = {"rankings": rankings, "theme": theme, "fortunes": fortunes}
    _cache[key] = result
    return result


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
