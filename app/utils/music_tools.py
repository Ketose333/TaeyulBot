import asyncio

from langchain_core.tools import tool

from app.utils.generation_defaults import (
    DEFAULT_MUSIC_COUNTRY,
    DEFAULT_MUSIC_RECOMMEND_COUNT,
    MUSIC_MOOD_TAGS,
)
from app.utils.music_recommend import analyze_mood, recommend_real_tracks


def make_music_tools(groq_api_key: str) -> list:
    """대화 중 자연어("우울한데 노래 추천해줘")로 트리거되는 LLM function-calling 도구."""

    @tool
    async def recommend_music(situation: str, korean_only: bool = False) -> str:
        """사용자의 기분/상황(situation)에 맞는 실제 발매곡을 추천한다.
        한국 가수 곡만 원하면 korean_only=True로 호출한다."""
        mood_analysis = await asyncio.to_thread(
            analyze_mood, situation, MUSIC_MOOD_TAGS, groq_api_key
        )
        tracks, _provider = await asyncio.to_thread(
            recommend_real_tracks,
            mood_analysis.mood,
            situation,
            mood_analysis.search_keywords,
            DEFAULT_MUSIC_RECOMMEND_COUNT,
            groq_api_key,
            DEFAULT_MUSIC_COUNTRY,
            "KR" if korean_only else None,
        )
        if not tracks:
            return "어울리는 곡을 찾지 못했습니다."
        return "\n".join(
            f"- {t.title} - {t.artist} ({t.links.get('Spotify', '')})" for t in tracks
        )

    return [recommend_music]
