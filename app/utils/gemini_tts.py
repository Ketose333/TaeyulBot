import asyncio
import io
import wave

from app.utils.gemini_client import _blocking_post, build_generate_content_body, extract_inline_data
from app.utils.generation_defaults import DEFAULT_TTS_MODEL, DEFAULT_TTS_VOICE


async def call_tts(api_key: str, model: str, text: str, voice: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    gen_cfg = {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
        },
    }
    body = build_generate_content_body([{"text": text}], gen_cfg)
    return await asyncio.to_thread(_blocking_post, url, body, error_prefix="Gemini TTS failed")


def extract_audio(payload: dict) -> tuple:
    return extract_inline_data(
        payload,
        default_mime="audio/wav",
        not_found_message="응답에서 오디오 데이터를 찾지 못함",
    )


def ext_from_mime(mime: str) -> str:
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "ogg" in mime:
        return "ogg"
    return "wav"


def maybe_wrap_pcm_to_wav(audio_bytes: bytes, mime: str) -> bytes:
    """Gemini가 raw PCM(예: audio/L16)을 반환하는 경우 WAV 컨테이너로 감싼다.
    이 처리를 생략하면 디스코드/일반 플레이어에서 재생 불가능한 헤더 없는 파일이 된다."""
    m = mime.lower()
    if "l16" not in m and "pcm" not in m:
        return audio_bytes

    sample_rate = 24000
    channels = 1

    parts = [p.strip() for p in mime.split(";")]
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip().lower()
        v = v.strip()
        if k == "rate":
            try:
                sample_rate = int(v)
            except ValueError:
                pass
        elif k == "channels":
            try:
                channels = int(v)
            except ValueError:
                pass

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(max(1, channels))
        wf.setsampwidth(2)
        wf.setframerate(max(8000, sample_rate))
        wf.writeframes(audio_bytes)
    return buf.getvalue()


async def generate_tts(
    api_key: str,
    text: str,
    *,
    model: str = DEFAULT_TTS_MODEL,
    voice: str = DEFAULT_TTS_VOICE,
) -> tuple:
    """(audio_bytes, ext)를 반환한다."""
    model_full = model if model.startswith("models/") else f"models/{model}"
    payload = await call_tts(api_key, model_full, text, voice)
    audio_bytes, mime = extract_audio(payload)
    audio_bytes = maybe_wrap_pcm_to_wav(audio_bytes, mime)
    return audio_bytes, ext_from_mime(mime)
