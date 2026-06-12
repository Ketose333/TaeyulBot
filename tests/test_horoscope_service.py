from datetime import date
from unittest.mock import patch
import pytest

from app.utils.saju_engine import ZODIAC_SIGNS

MOCK_FORTUNES = {sign: f"{sign} 테스트 운세입니다." for sign in ZODIAC_SIGNS}
MOCK_THEME = "갑자일 — 새 시작의 기운"


@patch("app.services.horoscope_service.generate_all_fortunes", return_value=MOCK_FORTUNES)
@patch("app.services.horoscope_service.get_daily_theme", return_value=MOCK_THEME)
@patch("app.services.horoscope_service.save_today")
@patch("app.services.horoscope_service.get_history", return_value={})
def test_get_today_fortune_structure(mock_history, mock_save, mock_theme, mock_fortunes, today):
    import app.services.horoscope_service as svc
    svc._cache.clear()

    result = svc.get_today_fortune(today)

    assert "rankings" in result
    assert "theme" in result
    assert "fortunes" in result
    assert len(result["rankings"]) == 12
    assert set(result["rankings"]) == set(ZODIAC_SIGNS)
    assert result["theme"] == MOCK_THEME
    mock_save.assert_called_once()


@patch("app.services.horoscope_service.get_lucky_item", return_value="도서관에서 집중력 UP")
@patch("app.services.horoscope_service.generate_all_fortunes", return_value=MOCK_FORTUNES)
@patch("app.services.horoscope_service.get_daily_theme", return_value=MOCK_THEME)
@patch("app.services.horoscope_service.save_today")
@patch("app.services.horoscope_service.get_history", return_value={})
def test_get_sign_fortune(mock_history, mock_save, mock_theme, mock_fortunes, mock_lucky, today):
    import app.services.horoscope_service as svc
    svc._cache.clear()

    result = svc.get_sign_fortune("사자자리", today)

    assert result["sign"] == "사자자리"
    assert result["rank"] is not None
    assert 1 <= result["rank"] <= 12
    assert "사자자리 테스트 운세입니다." in result["fortune"]
    assert result["lucky_item"] == "도서관에서 집중력 UP"


@patch("app.services.horoscope_service.generate_all_fortunes", return_value=MOCK_FORTUNES)
@patch("app.services.horoscope_service.get_daily_theme", return_value=MOCK_THEME)
@patch("app.services.horoscope_service.save_today")
@patch("app.services.horoscope_service.get_history", return_value={})
def test_cache_prevents_duplicate_calls(mock_history, mock_save, mock_theme, mock_fortunes, today):
    import app.services.horoscope_service as svc
    svc._cache.clear()

    svc.get_today_fortune(today)
    svc.get_today_fortune(today)

    # 캐시 덕분에 사주 엔진은 1회만 호출되어야 함
    assert mock_fortunes.call_count == 1
