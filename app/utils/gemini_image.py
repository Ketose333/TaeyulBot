import asyncio
import base64
import json
import urllib.error
import urllib.request

from app.utils.generation_defaults import (
    DEFAULT_IMAGE_ASPECT_RATIO,
    DEFAULT_IMAGE_FALLBACK_MODEL,
    DEFAULT_IMAGE_MODEL,
)
from app.utils.image_rules import avatar_lock_prompt, normalize_request_prompt


def _blocking_post(url: str, body: dict) -> dict:
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
        raise RuntimeError(f"Gemini image generation failed ({e.code}): {payload}") from e


async def call_generate(
    api_key: str,
    model: str,
    prompt: str,
    *,
    ref_image_bytes: bytes = None,
    ref_image_mime: str = "image/png",
    lock_avatar: bool = True,
    allow_2d: bool = False,
    profile: str = "taeyul",
    aspect_ratio: str = "",
) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"

    prompt_text = (
        avatar_lock_prompt(prompt, allow_2d=allow_2d, model=model, profile=profile)
        if (ref_image_bytes and lock_avatar)
        else normalize_request_prompt(prompt)
    )
    parts = []

    if ref_image_bytes:
        b64 = base64.b64encode(ref_image_bytes).decode("ascii")
        parts.append({"inline_data": {"mime_type": ref_image_mime, "data": b64}})

    parts.append({"text": prompt_text})

    gen_cfg = {"responseModalities": ["TEXT", "IMAGE"]}
    ar = (aspect_ratio or "").strip()
    if ar:
        gen_cfg["imageConfig"] = {"aspectRatio": ar}

    body = {"contents": [{"parts": parts}], "generationConfig": gen_cfg}
    return await asyncio.to_thread(_blocking_post, url, body)


def extract_image(payload: dict) -> tuple:
    candidates = payload.get("candidates", [])
    for c in candidates:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                mime = (inline.get("mimeType") or inline.get("mime_type") or "image/jpeg").lower()
                return base64.b64decode(inline["data"]), mime
    raise RuntimeError("응답에서 이미지 데이터를 찾지 못함")


def ext_from_mime(mime: str) -> str:
    if "png" in mime:
        return "png"
    if "webp" in mime:
        return "webp"
    return "jpg"


def _with_models_prefix(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


async def generate_image_with_fallback(
    api_key: str,
    prompt: str,
    *,
    ref_image_bytes: bytes,
    ref_image_mime: str = "image/png",
    model: str = DEFAULT_IMAGE_MODEL,
    allow_2d: bool = False,
    profile: str = "taeyul",
    aspect_ratio: str = DEFAULT_IMAGE_ASPECT_RATIO,
) -> tuple:
    """(img_bytes, mime, model_used)를 반환한다. 기본 모델 실패 시 폴백 모델로 재시도한다."""
    primary = _with_models_prefix(model)
    model_chain = [primary]
    if primary == _with_models_prefix(DEFAULT_IMAGE_MODEL):
        model_chain.append(_with_models_prefix(DEFAULT_IMAGE_FALLBACK_MODEL))

    last_err = None
    for model_try in model_chain:
        try:
            payload = await call_generate(
                api_key,
                model_try,
                prompt,
                ref_image_bytes=ref_image_bytes,
                ref_image_mime=ref_image_mime,
                allow_2d=allow_2d,
                profile=profile,
                aspect_ratio=aspect_ratio,
            )
            img_bytes, mime = extract_image(payload)
            return img_bytes, mime, model_try
        except Exception as e:
            last_err = e

    raise last_err
