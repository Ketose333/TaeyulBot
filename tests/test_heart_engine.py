import pytest

from app.utils.heart_engine import normalize_hex, render_heart


def test_normalize_hex_adds_missing_hash():
    assert normalize_hex("112233") == "#112233"


def test_normalize_hex_keeps_existing_hash():
    assert normalize_hex("#112233") == "#112233"


def test_normalize_hex_rejects_invalid_input():
    with pytest.raises(ValueError):
        normalize_hex("not-a-color")


def test_render_heart_returns_png_bytes():
    buf = render_heart("#112233")

    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
