import pytest

from app.utils.music_recommend import (
    RealTrack,
    _groq_json_chat,
    analyze_mood,
    infer_mood_from_text,
    itunes_search,
    matches_country,
    parse_mood_response,
    parse_song_response,
    recommend_real_tracks,
    service_links,
    verify_track,
)


def test_infer_mood_from_text_matches_keyword():
    best_tag, counts = infer_mood_from_text("오늘 진짜 우울하고 눈물난다", ["happy", "dark"])
    assert best_tag == "dark"
    assert counts["dark"] >= 1


def test_infer_mood_from_text_no_match_returns_none():
    best_tag, counts = infer_mood_from_text("아무 감정 없는 문장", ["happy", "dark"])
    assert best_tag is None
    assert counts == {"happy": 0, "dark": 0}


def test_parse_mood_response_valid_json():
    raw = '{"mood": "happy", "confidence": 0.8, "reason": "설렘", "search_keywords": ["pop"]}'
    parsed = parse_mood_response(raw, ["happy", "dark"])
    assert parsed["mood"] == "happy"
    assert parsed["confidence"] == 0.8
    assert parsed["search_keywords"] == ["pop"]


def test_parse_mood_response_invalid_mood_returns_none():
    raw = '{"mood": "unknown_tag", "confidence": 0.5, "reason": "x"}'
    assert parse_mood_response(raw, ["happy", "dark"]) is None


def test_parse_mood_response_no_json_returns_none():
    assert parse_mood_response("이건 JSON이 아님", ["happy"]) is None


def test_parse_song_response_extracts_valid_songs():
    raw = '{"songs": [{"title": "T1", "artist": "A1", "reason": "R1"}, {"title": "", "artist": "A2"}]}'
    triples = parse_song_response(raw)
    assert triples == [("T1", "A1", "R1")]


def test_parse_song_response_no_json_returns_empty_list():
    assert parse_song_response("no json here") == []


def test_service_links_contains_all_three_services():
    links = service_links("Song", "Artist")
    assert set(links.keys()) == {"Spotify", "YouTube Music", "Apple Music"}
    assert "%20" in links["Spotify"]


def test_matches_country_by_genre():
    track = RealTrack(title="곡", artist="가수", genre="K-Pop")
    assert matches_country(track, "KR") is True


def test_matches_country_by_script():
    track = RealTrack(title="사랑해", artist="아이유", genre="Pop")
    assert matches_country(track, "KR") is True


def test_matches_country_no_match():
    track = RealTrack(title="Love", artist="John Smith", genre="Pop")
    assert matches_country(track, "KR") is False


def test_matches_country_unknown_country_returns_true():
    track = RealTrack(title="Song", artist="Artist")
    assert matches_country(track, "ZZ") is True


def test_groq_json_chat_no_api_key_returns_none():
    assert _groq_json_chat("prompt", "") is None


def test_groq_json_chat_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"mood": "happy"}'}}]}

    monkeypatch.setattr(
        "app.utils.music_recommend.requests.post", lambda *a, **kw: FakeResponse()
    )
    result = _groq_json_chat("prompt", "fake-key")
    assert result == '{"mood": "happy"}'


def test_groq_json_chat_request_error_returns_none(monkeypatch):
    import requests

    def raise_error(*a, **kw):
        raise requests.RequestException("boom")

    monkeypatch.setattr("app.utils.music_recommend.requests.post", raise_error)
    assert _groq_json_chat("prompt", "fake-key") is None


def test_analyze_mood_falls_back_to_keyword_when_no_api_key():
    result = analyze_mood("오늘 너무 신나고 즐거워", ["happy", "dark"], groq_api_key="")
    assert result.mood == "happy"
    assert result.provider == "keyword"


def test_itunes_search_parses_results(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "trackName": "Song",
                        "artistName": "Artist",
                        "collectionName": "Album",
                        "primaryGenreName": "Pop",
                        "trackViewUrl": "https://music.apple.com/x",
                    }
                ]
            }

    monkeypatch.setattr("app.utils.music_recommend.requests.get", lambda *a, **kw: FakeResponse())
    tracks = itunes_search("song")
    assert len(tracks) == 1
    assert tracks[0].title == "Song"
    assert tracks[0].artist == "Artist"


def test_verify_track_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr("app.utils.music_recommend.itunes_search", lambda *a, **kw: [])
    assert verify_track("Fake Title", "Fake Artist") is None


def test_recommend_real_tracks_falls_back_to_itunes_when_no_groq_key(monkeypatch):
    fake_track = RealTrack(title="Song", artist="Artist", genre="Pop", links=service_links("Song", "Artist"))
    monkeypatch.setattr(
        "app.utils.music_recommend.itunes_search", lambda *a, **kw: [fake_track]
    )
    tracks, provider = recommend_real_tracks("happy", "신나", k=1, groq_api_key="")
    assert provider == "itunes"
    assert len(tracks) == 1
    assert tracks[0].title == "Song"


def test_recommend_real_tracks_no_results_returns_empty_list(monkeypatch):
    monkeypatch.setattr("app.utils.music_recommend.itunes_search", lambda *a, **kw: [])
    tracks, provider = recommend_real_tracks("happy", "신나", k=3, groq_api_key="")
    assert tracks == []
    assert provider == "itunes"
