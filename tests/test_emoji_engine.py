from app.utils.emoji_engine import render_text_emoji, romanize_hangul


def test_romanize_hangul_uses_emoji_names_override():
    assert romanize_hangul("잘") == "jal_emoji"


def test_romanize_hangul_falls_back_to_syllable_concat():
    assert romanize_hangul("잘살게") == "jalsalge"


def test_romanize_hangul_ascii_passthrough():
    assert romanize_hangul("Hi") == "hi"


def test_render_text_emoji_returns_name_and_png_bytes():
    name, buf = render_text_emoji("잘살게")

    assert name == "jalsalge"
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
