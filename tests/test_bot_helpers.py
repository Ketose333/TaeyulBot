from app.bot import _build_discord_files, _truncate_for_discord


def test_truncate_for_discord_short_text_untouched():
    text = "짧은 메시지"
    assert _truncate_for_discord(text) == text


def test_truncate_for_discord_long_text_is_cut_to_limit():
    text = "가" * 3000
    result = _truncate_for_discord(text, limit=2000)
    assert len(result) <= 2000
    assert result.startswith("가" * 10)


def test_build_discord_files_converts_attachments():
    attachments = [(b"fake-bytes", "a.png"), (b"more-bytes", "b.wav")]
    files = _build_discord_files(attachments)
    assert len(files) == 2
    assert files[0].filename == "a.png"
    assert files[1].filename == "b.wav"


def test_build_discord_files_empty_list():
    assert _build_discord_files([]) == []
