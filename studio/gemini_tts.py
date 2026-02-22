#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

SAFE_DEFAULT_OUTPUT_DIR = Path("/home/user/.openclaw/media/audio").resolve()
LEGACY_OUTPUT_DIR = Path("/home/user/.openclaw/workspace/output").resolve()

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    for _p in _Path(__file__).resolve().parents:
        if (_p / 'utility').exists():
            sys.path.append(str(_p))
            break
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv


def _force_utf8_stdio() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9가-힣]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "tts"


def _resolve_unique_name(out_dir: Path, name: str) -> str:
    p = Path(name)
    stem, suf = p.stem, p.suffix
    cand = out_dir / f"{stem}{suf}"
    i = 2
    while cand.exists():
        cand = out_dir / f"{stem}_{i}{suf}"
        i += 1
    return cand.name


def call_tts(api_key: str, model: str, text: str, voice: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            },
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini TTS failed ({e.code}): {payload}") from e


def extract_audio(payload: dict) -> tuple[bytes, str]:
    candidates = payload.get("candidates", [])
    for c in candidates:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                mime = (inline.get("mimeType") or inline.get("mime_type") or "audio/wav").lower()
                return base64.b64decode(inline["data"]), mime
    raise RuntimeError("응답에서 오디오 데이터를 찾지 못함")


def ext_from_mime(mime: str) -> str:
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "ogg" in mime:
        return "ogg"
    return "wav"


def maybe_wrap_pcm_to_wav(audio_bytes: bytes, mime: str) -> bytes:
    """Gemini can return raw PCM (e.g., audio/L16). Wrap it into a valid WAV container."""
    m = mime.lower()
    if "l16" not in m and "pcm" not in m:
        return audio_bytes

    sample_rate = 24000
    channels = 1

    # Example mime: audio/L16;rate=24000;channels=1
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
            except Exception:
                pass
        elif k == "channels":
            try:
                channels = int(v)
            except Exception:
                pass

    # 16-bit PCM little-endian assumed for L16 output
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(max(1, channels))
        wf.setsampwidth(2)
        wf.setframerate(max(8000, sample_rate))
        wf.writeframes(audio_bytes)
    return buf.getvalue()


def main() -> int:
    _force_utf8_stdio()
    load_env_prefer_dotenv()

    ap = argparse.ArgumentParser(description="Generate TTS audio using Gemini API")
    ap.add_argument("text", help="Text to synthesize")
    ap.add_argument("--model", default="gemini-2.5-flash-preview-tts", help="Model id (without models/ prefix)")
    ap.add_argument("--voice", default="Fenrir", help="Prebuilt voice name")
    ap.add_argument("--out-dir", default=str(SAFE_DEFAULT_OUTPUT_DIR), help="Output directory")
    ap.add_argument("--name", default="", help="Output filename (optional)")
    ap.add_argument("--emit-media", action="store_true", help="Print MEDIA:relative_path")
    args = ap.parse_args()

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("Missing GEMINI_API_KEY or GOOGLE_API_KEY", file=sys.stderr)
        return 2

    model = args.model if args.model.startswith("models/") else f"models/{args.model}"

    try:
        payload = call_tts(api_key, model, args.text, args.voice)
        audio_bytes, mime = extract_audio(payload)
        audio_bytes = maybe_wrap_pcm_to_wav(audio_bytes, mime)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve()
    if out_dir == LEGACY_OUTPUT_DIR:
        out_dir = SAFE_DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = ext_from_mime(mime)
    default_name = f"{slugify(args.text)[:60]}.{ext}"

    if args.name.strip():
        raw = args.name.strip()
        if "." not in Path(raw).name:
            raw = f"{raw}.{ext}"
        name = raw
    else:
        name = default_name

    name = _resolve_unique_name(out_dir, name)
    out = (out_dir / name).resolve()
    out.write_bytes(audio_bytes)

    cwd = Path.cwd().resolve()
    try:
        rel = out.relative_to(cwd)
        media_path = f"./{rel.as_posix()}"
    except ValueError:
        media_path = out.as_posix()

    if args.emit_media:
        print(f"MEDIA:{media_path}")
    else:
        print(f"AUDIO:{media_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
