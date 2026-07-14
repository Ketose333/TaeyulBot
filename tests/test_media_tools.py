import pytest

from app.utils.media_tools import MediaSink, make_media_tools


@pytest.mark.asyncio
async def test_generate_taeyul_image_appends_to_sink_and_limits_to_once(monkeypatch):
    monkeypatch.setattr(
        "app.utils.media_tools._load_avatar_bytes", lambda: b"fake-avatar-bytes"
    )

    async def fake_generate(*args, **kwargs):
        return b"fake-png-bytes", "image/png", "models/nano-banana-pro-preview"

    monkeypatch.setattr("app.utils.media_tools.generate_image_with_fallback", fake_generate)

    sink = MediaSink()
    image_tool, _ = make_media_tools(sink, "fake-api-key")

    result1 = await image_tool.ainvoke({"prompt": "웃는 얼굴"})
    assert "생성 완료" in result1
    assert len(sink.items) == 1
    assert sink.items[0][0] == b"fake-png-bytes"
    assert sink.items[0][1].endswith(".png")

    result2 = await image_tool.ainvoke({"prompt": "다른 얼굴"})
    assert "이미 1장 생성" in result2
    assert len(sink.items) == 1  # 두 번째 호출은 추가되지 않아야 함


@pytest.mark.asyncio
async def test_generate_taeyul_image_no_api_key_returns_message():
    sink = MediaSink()
    image_tool, _ = make_media_tools(sink, "")

    result = await image_tool.ainvoke({"prompt": "웃는 얼굴"})
    assert "사용할 수 없습니다" in result
    assert sink.items == []


@pytest.mark.asyncio
async def test_generate_taeyul_voice_appends_to_sink_and_limits_to_once(monkeypatch):
    async def fake_tts(*args, **kwargs):
        return b"fake-wav-bytes", "wav"

    monkeypatch.setattr("app.utils.media_tools.generate_tts", fake_tts)

    sink = MediaSink()
    _, voice_tool = make_media_tools(sink, "fake-api-key")

    result1 = await voice_tool.ainvoke({"text": "안녕"})
    assert "생성 완료" in result1
    assert len(sink.items) == 1
    assert sink.items[0][1].endswith(".wav")

    result2 = await voice_tool.ainvoke({"text": "또 안녕"})
    assert "이미 1개 생성" in result2
    assert len(sink.items) == 1


@pytest.mark.asyncio
async def test_generate_taeyul_image_failure_returns_message_without_appending(monkeypatch):
    monkeypatch.setattr(
        "app.utils.media_tools._load_avatar_bytes", lambda: b"fake-avatar-bytes"
    )

    async def failing_generate(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.utils.media_tools.generate_image_with_fallback", failing_generate)

    sink = MediaSink()
    image_tool, _ = make_media_tools(sink, "fake-api-key")

    result = await image_tool.ainvoke({"prompt": "웃는 얼굴"})
    assert "실패" in result
    assert sink.items == []
