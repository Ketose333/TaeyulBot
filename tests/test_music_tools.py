import pytest

from app.utils.music_recommend import RealTrack, service_links
from app.utils.music_tools import make_music_tools


def test_make_music_tools_returns_single_tool():
    tools = make_music_tools("fake-groq-key")
    names = {t.name for t in tools}
    assert names == {"recommend_music"}


@pytest.mark.asyncio
async def test_recommend_music_no_tracks_returns_message(monkeypatch):
    monkeypatch.setattr(
        "app.utils.music_tools.analyze_mood",
        lambda text, tags, key: type(
            "MoodAnalysis", (), {"mood": "happy", "search_keywords": []}
        )(),
    )
    monkeypatch.setattr(
        "app.utils.music_tools.recommend_real_tracks", lambda *a, **kw: ([], "itunes")
    )

    (tool,) = make_music_tools("fake-groq-key")
    result = await tool.ainvoke({"situation": "신나는 노래"})
    assert result == "어울리는 곡을 찾지 못했습니다."


@pytest.mark.asyncio
async def test_recommend_music_returns_formatted_track_list(monkeypatch):
    fake_track = RealTrack(
        title="Song", artist="Artist", links=service_links("Song", "Artist")
    )

    monkeypatch.setattr(
        "app.utils.music_tools.analyze_mood",
        lambda text, tags, key: type(
            "MoodAnalysis", (), {"mood": "happy", "search_keywords": []}
        )(),
    )
    monkeypatch.setattr(
        "app.utils.music_tools.recommend_real_tracks",
        lambda *a, **kw: ([fake_track], "groq"),
    )

    (tool,) = make_music_tools("fake-groq-key")
    result = await tool.ainvoke({"situation": "신나는 노래"})
    assert "Song - Artist" in result


@pytest.mark.asyncio
async def test_recommend_music_korean_only_passes_kr_artist_country(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.utils.music_tools.analyze_mood",
        lambda text, tags, key: type(
            "MoodAnalysis", (), {"mood": "happy", "search_keywords": []}
        )(),
    )

    def fake_recommend(mood, user_text, keywords, k, key, country, artist_country):
        captured["artist_country"] = artist_country
        return [], "itunes"

    monkeypatch.setattr("app.utils.music_tools.recommend_real_tracks", fake_recommend)

    (tool,) = make_music_tools("fake-groq-key")
    await tool.ainvoke({"situation": "신나는 노래", "korean_only": True})
    assert captured["artist_country"] == "KR"
