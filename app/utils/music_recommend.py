"""자연어 기분/상황 → 실제 발매곡 추천.

Groq LLM이 후보곡을 제안하고 iTunes Search API(무료, 키 불필요)로 검증해
환각곡을 걸러낸 뒤 Spotify/YouTube Music/Apple Music 검색 링크만 반환한다.
오디오는 재생하지 않는다. personal/music-mood-recs의
src/llm/{mood_analyzer,music_search}.py를 Ollama 티어 없이 이식.
"""

from __future__ import annotations

import json
import random
import re
import urllib.parse
from dataclasses import dataclass, field

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
LLM_TIMEOUT = 30

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_TIMEOUT = 10

MOOD_KEYWORDS: dict[str, list[str]] = {
    "happy": ["행복", "기쁘", "기뻐", "즐겁", "신나", "설레", "웃음", "웃기", "들뜨", "유쾌"],
    "energetic": ["에너지", "파워", "운동", "헬스", "달리", "파이팅", "격렬", "흥분", "활기", "신남"],
    "relaxing": ["편안", "휴식", "잠", "졸려", "힐링", "차분", "여유", "평화", "느긋", "안정"],
    "film": ["영화", "웅장", "드라마틱", "서사", "영상", "스토리", "장엄", "긴장감", "몰입"],
    "dark": ["우울", "슬픔", "슬프", "어둡", "외롭", "쓸쓸", "그리움", "눈물", "힘들", "지치", "불안"],
}

MOOD_SEARCH_TERMS: dict[str, list[str]] = {
    "happy": ["happy upbeat feel good pop", "sunny cheerful pop hits", "feel good summer pop"],
    "energetic": ["energetic workout power up", "high energy dance pop", "pump up gym anthem"],
    "relaxing": ["relaxing calm acoustic chill", "chill lofi calm", "soft acoustic mellow"],
    "film": ["epic cinematic soundtrack score", "orchestral movie score", "dramatic film score"],
    "dark": ["dark moody melancholic", "brooding dark alternative", "melancholic minor key"],
}

_COUNTRY_FILTERS: dict[str, dict] = {
    "KR": {
        "prompt_label": "한국 국내 가수(K-pop/국내 발매곡)",
        "genres": {"K-Pop", "Korean Pop", "Trot", "Korean Hip-Hop", "Korean R&B/Soul"},
        "script_re": re.compile(r"[가-힣]"),
        "search_suffix": "케이팝",
    },
    "JP": {
        "prompt_label": "일본 가수(J-pop/국내 발매곡)",
        "genres": {"J-Pop", "J-Rock", "Anime", "Japanese Pop"},
        "script_re": re.compile(r"[぀-ヿ]"),
        "search_suffix": "제이팝",
    },
}


def infer_mood_from_text(text: str, tags: list[str]) -> tuple[str | None, dict[str, int]]:
    """텍스트를 태그별 키워드로 스코어링해 가장 잘 맞는 태그를 고른다(LLM 실패 시 최종 폴백)."""
    counts = {tag: 0 for tag in tags}
    for tag in tags:
        for kw in MOOD_KEYWORDS.get(tag, []):
            if kw in text:
                counts[tag] += 1
    best_tag = max(counts, key=counts.get) if counts else None
    if best_tag is not None and counts[best_tag] == 0:
        best_tag = None
    return best_tag, counts


@dataclass
class MoodAnalysis:
    mood: str
    confidence: float
    reason: str
    search_keywords: list[str] = field(default_factory=list)
    provider: str = "keyword"  # "groq" | "keyword"


def _groq_json_chat(prompt: str, api_key: str, timeout: int = LLM_TIMEOUT) -> str | None:
    """Groq REST API에 JSON 모드로 1회 호출. 실패/키 없음 시 None(호출부는 다음 폴백 단계로)."""
    if not api_key:
        return None
    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None


def build_mood_prompt(text: str, tags: list[str]) -> str:
    tag_list = ", ".join(tags)
    return (
        "당신은 음악 무드 분석가입니다. 사용자의 문장을 읽고 아래 5개 무드 태그 중 "
        "가장 어울리는 하나를 고르세요.\n"
        f"허용 태그(반드시 이 중 하나만): {tag_list}\n\n"
        "규칙:\n"
        "- 반드시 JSON 객체 하나만 출력하세요. 다른 텍스트/마크다운 금지.\n"
        '- 형식: {"mood": "<태그>", "confidence": 0.0~1.0, '
        '"reason": "<한국어 한두 문장>", "search_keywords": ["<영어 음악 검색 키워드 2~4개>"]}\n'
        "- search_keywords는 이 기분에 맞는 실제 음원을 찾기 위한 영어 검색어입니다 "
        '(예: "upbeat pop", "calm acoustic").\n\n'
        f"사용자 문장: {text}"
    )


def parse_mood_response(raw: str, tags: list[str]) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    mood = str(data.get("mood", "")).strip().lower()
    if mood not in tags:
        return None
    try:
        confidence = min(max(float(data.get("confidence", 0.5)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.5
    keywords = data.get("search_keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    keywords = [str(k).strip() for k in keywords if str(k).strip()][:4]
    return {
        "mood": mood,
        "confidence": confidence,
        "reason": str(data.get("reason", "")).strip(),
        "search_keywords": keywords,
    }


def analyze_mood(text: str, tags: list[str], groq_api_key: str | None = None) -> MoodAnalysis:
    """자유 텍스트를 5개 무드 태그 중 하나로 매핑한다. Groq 실패/미설정 시 키워드 휴리스틱으로 대체."""
    raw = _groq_json_chat(build_mood_prompt(text, tags), groq_api_key or "")
    if raw is not None:
        parsed = parse_mood_response(raw, tags)
        if parsed is not None:
            return MoodAnalysis(provider="groq", **parsed)

    best_tag, counts = infer_mood_from_text(text, tags)
    if best_tag is None:
        best_tag = tags[0]
        reason = "키워드 매칭 없음 — 기본 태그로 대체 (LLM 미사용)"
    else:
        reason = f"한국어 감정 키워드 {counts[best_tag]}건 매칭 (LLM 미사용)"
    return MoodAnalysis(
        mood=best_tag,
        confidence=min(counts.get(best_tag, 0) / 3.0, 1.0),
        reason=reason,
        search_keywords=[],
        provider="keyword",
    )


@dataclass
class RealTrack:
    """실제 검증된 발매곡 1건. 서비스별 검색 링크만 담고 오디오는 담지 않는다."""

    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""
    genre: str = ""
    links: dict[str, str] = field(default_factory=dict)
    reason: str = ""


def matches_country(track: RealTrack, country: str) -> bool:
    cfg = _COUNTRY_FILTERS.get(country)
    if cfg is None:
        return True
    if track.genre in cfg["genres"]:
        return True
    return bool(cfg["script_re"].search(track.title) or cfg["script_re"].search(track.artist))


def service_links(title: str, artist: str, itunes_url: str = "") -> dict[str, str]:
    q = urllib.parse.quote(f"{title} {artist}")
    return {
        "Spotify": f"https://open.spotify.com/search/{q}",
        "YouTube Music": f"https://music.youtube.com/search?q={q}",
        "Apple Music": itunes_url or f"https://music.apple.com/kr/search?term={q}",
    }


def _to_real_track(item: dict) -> RealTrack:
    title = item.get("trackName", "")
    artist = item.get("artistName", "")
    return RealTrack(
        title=title,
        artist=artist,
        album=item.get("collectionName", ""),
        artwork_url=item.get("artworkUrl100", ""),
        genre=item.get("primaryGenreName", ""),
        links=service_links(title, artist, item.get("trackViewUrl", "")),
    )


def itunes_search(term: str, limit: int = 5, country: str = "KR") -> list[RealTrack]:
    resp = requests.get(
        ITUNES_SEARCH_URL,
        params={"term": term, "media": "music", "entity": "song", "limit": limit, "country": country},
        timeout=ITUNES_TIMEOUT,
    )
    resp.raise_for_status()
    return [_to_real_track(r) for r in resp.json().get("results", []) if r.get("trackName")]


def verify_track(title: str, artist: str, country: str = "KR") -> RealTrack | None:
    """실존 여부 확인용 anti-hallucination 게이트. LLM이 지어낸 곡은 검색 결과가 없어 걸러진다."""
    try:
        results = itunes_search(f"{title} {artist}", limit=1, country=country)
    except requests.RequestException:
        return None
    return results[0] if results else None


def build_song_prompt(
    mood: str, user_text: str, k: int, artist_country: str | None = None,
    exclude: list[tuple[str, str]] | None = None,
) -> str:
    context = f"\n사용자의 원래 문장(분위기 참고): {user_text}" if user_text else ""
    country_rule = ""
    if artist_country and artist_country in _COUNTRY_FILTERS:
        label = _COUNTRY_FILTERS[artist_country]["prompt_label"]
        country_rule = f"\n- 반드시 {label}만 추천하세요. 다른 국가 아티스트는 제외."
    exclude_rule = ""
    if exclude:
        exclude_list = ", ".join(f"{t} - {a}" for t, a in exclude)
        exclude_rule = f"\n- 다음 곡은 이미 추천했으니 절대 다시 추천하지 마세요: {exclude_list}"
    return (
        f"'{mood}' 무드에 어울리는, 실제로 발매된 유명한 곡을 {k + 3}개 추천하세요."
        f"{context}\n\n"
        "규칙:\n"
        "- 실존하는 곡만. 확실하지 않은 곡은 넣지 마세요."
        f"{country_rule}{exclude_rule}\n"
        "- 반드시 JSON 객체 하나만 출력: "
        '{"songs": [{"title": "<곡명>", "artist": "<아티스트>", '
        '"reason": "<이 곡이 왜 이 무드와 어울리는지 한국어 1문장. 가사·줄거리 등 사실 주장 금지, 분위기/장르 톤만 언급>"}, ...]}\n'
        "- 다양한 아티스트로 구성하세요 (한 아티스트 최대 1곡)."
    )


def parse_song_response(raw: str) -> list[tuple[str, str, str]]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    triples: list[tuple[str, str, str]] = []
    for song in data.get("songs", []) if isinstance(data, dict) else []:
        if not isinstance(song, dict):
            continue
        title = str(song.get("title", "")).strip()
        artist = str(song.get("artist", "")).strip()
        reason = str(song.get("reason", "")).strip()
        if title and artist:
            triples.append((title, artist, reason))
    return triples


def recommend_real_tracks(
    mood: str,
    user_text: str = "",
    search_keywords: list[str] | None = None,
    k: int = 5,
    groq_api_key: str | None = None,
    country: str = "KR",
    artist_country: str | None = None,
    exclude: list[tuple[str, str]] | None = None,
) -> tuple[list[RealTrack], str]:
    """Top-k 실존 발매곡. 반환: (tracks, provider). provider는 "groq"(LLM 후보 iTunes 검증
    성공) 또는 "itunes"(키워드 검색만으로 채움)."""
    tracks: list[RealTrack] = []
    provider = "itunes"
    seen: set[tuple[str, str]] = {(t.lower(), a.lower()) for t, a in (exclude or [])}

    raw = _groq_json_chat(
        build_song_prompt(mood, user_text, k, artist_country=artist_country, exclude=exclude),
        groq_api_key or "",
    )
    if raw is not None:
        for title, artist, reason in parse_song_response(raw):
            if len(tracks) >= k:
                break
            found = verify_track(title, artist, country=country)
            if found is None:
                continue
            if artist_country and not matches_country(found, artist_country):
                continue
            key = (found.title.lower(), found.artist.lower())
            if key in seen:
                continue
            found.reason = reason or f"'{mood}' 무드와 어울리는 곡으로 LLM이 추천했습니다."
            seen.add(key)
            tracks.append(found)
        if tracks:
            provider = "groq"

    if len(tracks) < k:
        if search_keywords:
            term = " ".join(search_keywords)
        else:
            term = random.choice(MOOD_SEARCH_TERMS.get(mood, [f"{mood} music"]))
        if artist_country and artist_country in _COUNTRY_FILTERS:
            term = f"{term} {_COUNTRY_FILTERS[artist_country]['search_suffix']}"
        try:
            candidates = itunes_search(term, limit=max(k * 3, 25), country=country)
        except requests.RequestException:
            candidates = []
        if artist_country:
            candidates = [c for c in candidates if matches_country(c, artist_country)]
        random.shuffle(candidates)
        for allow_repeat_artist in (False, True):
            for found in candidates:
                if len(tracks) >= k:
                    break
                key = (found.title.lower(), found.artist.lower())
                if key in seen:
                    continue
                if not allow_repeat_artist and any(
                    t.artist.lower() == found.artist.lower() for t in tracks
                ):
                    continue
                found.reason = f"'{mood}' 무드 검색으로 찾은 {found.genre or '추천'} 곡입니다."
                seen.add(key)
                tracks.append(found)

    return tracks[:k], provider
