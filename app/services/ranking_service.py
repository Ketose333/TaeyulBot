import random
import hashlib
from datetime import date

from app.utils.saju_engine import ZODIAC_SIGNS

BASE_SCORE_MIN = 60
BASE_SCORE_MAX = 100
REPEAT_PENALTY = 30
THEME_SEEDS = [
    "불", "물", "땅", "바람", "빛", "어둠", "꿈", "현실", "변화", "안정",
    "열정", "지혜", "사랑", "용기", "도전", "휴식", "성장", "조화", "자유", "신비",
]


def _date_seed(today: date) -> int:
    digest = hashlib.md5(today.isoformat().encode()).hexdigest()
    return int(digest[:8], 16)


def pick_theme_seed(today: date) -> str:
    rng = random.Random(_date_seed(today))
    return rng.choice(THEME_SEEDS)


def generate_ranking(today: date, history: dict) -> list[str]:
    rng = random.Random(_date_seed(today))

    scores: dict[str, float] = {
        sign: rng.uniform(BASE_SCORE_MIN, BASE_SCORE_MAX)
        for sign in ZODIAC_SIGNS
    }

    # 최근 3일 1위 별자리에 페널티 → 연속 상위권 방지
    from app.utils.date_utils import get_recent_top_signs
    recent_tops = get_recent_top_signs(history, days=3, reference_date=today)
    for sign in recent_tops:
        if sign in scores:
            scores[sign] -= REPEAT_PENALTY

    return sorted(ZODIAC_SIGNS, key=lambda s: scores[s], reverse=True)
