import base64
import wave
import io

import pytest

from app.utils.gemini_image import ext_from_mime as image_ext_from_mime
from app.utils.gemini_image import extract_image
from app.utils.gemini_tts import ext_from_mime as audio_ext_from_mime
from app.utils.gemini_tts import maybe_wrap_pcm_to_wav


def _payload_with_inline_data(mime: str, data: bytes) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}}
                    ]
                }
            }
        ]
    }


def test_extract_image_returns_bytes_and_mime():
    raw = b"\x89PNG\r\n\x1a\nfake"
    payload = _payload_with_inline_data("image/png", raw)
    img_bytes, mime = extract_image(payload)
    assert img_bytes == raw
    assert mime == "image/png"


def test_extract_image_raises_when_no_image_data():
    with pytest.raises(RuntimeError):
        extract_image({"candidates": [{"content": {"parts": [{"text": "no image here"}]}}]})


def test_image_ext_from_mime():
    assert image_ext_from_mime("image/png") == "png"
    assert image_ext_from_mime("image/webp") == "webp"
    assert image_ext_from_mime("image/jpeg") == "jpg"


def test_audio_ext_from_mime():
    assert audio_ext_from_mime("audio/mpeg") == "mp3"
    assert audio_ext_from_mime("audio/ogg") == "ogg"
    assert audio_ext_from_mime("audio/wav") == "wav"


def test_maybe_wrap_pcm_to_wav_wraps_raw_l16():
    raw_pcm = (b"\x01\x00" * 100)
    wrapped = maybe_wrap_pcm_to_wav(raw_pcm, "audio/L16;rate=24000;channels=1")

    with wave.open(io.BytesIO(wrapped), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000
        assert wf.getsampwidth() == 2
        assert wf.readframes(wf.getnframes()) == raw_pcm


def test_maybe_wrap_pcm_to_wav_passthrough_for_already_wav():
    raw = b"RIFF....WAVEfake"
    assert maybe_wrap_pcm_to_wav(raw, "audio/wav") == raw
