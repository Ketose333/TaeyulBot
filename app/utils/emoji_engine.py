from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STYLE_PATH = ASSETS_DIR / "emoji_style.json"

INITIALS = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "",
            "j", "jj", "ch", "k", "t", "p", "h"]
VOWELS = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae",
          "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
FINALS = ["", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lk", "lm", "lb",
          "ls", "lt", "lp", "lh", "m", "p", "ps", "t", "t", "ng", "t", "t",
          "k", "t", "p", "t"]


def _load_style() -> dict:
    with STYLE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def romanize_hangul(text: str, style: dict | None = None) -> str:
    style = style or _load_style()
    names = style.get("emoji_names", {})
    if text in names:
        return names[text]

    parts = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            syllable = code - 0xAC00
            initial = syllable // 588
            vowel = (syllable % 588) // 28
            final = syllable % 28
            parts.append(INITIALS[initial] + VOWELS[vowel] + FINALS[final])
        elif char.isalnum():
            parts.append(char.lower())
        elif char in (" ", "-", "_"):
            parts.append("_")

    name = "_".join(filter(None, "".join(parts).split("_")))
    if len(name) < 2:
        name = f"{name}_emoji" if name else "emoji"
    return name


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path, style: dict) -> ImageFont.FreeTypeFont:
    canvas = style["canvas"]
    layout = style["layout"]
    paint = style["paint"]
    scale = canvas["scale"]
    max_w = int(canvas["width"] * layout["max_width_ratio"] * scale)
    max_h = int(canvas["height"] * layout["max_height_ratio"] * scale)
    stroke_w = int(paint["stroke_width_px"] * scale)

    lo, hi = 100 * scale, 980 * scale
    best_size = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(str(font_path), mid)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_w and text_h <= max_h:
            best_size = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return ImageFont.truetype(str(font_path), best_size)


def render_text_emoji(text: str, style: dict | None = None) -> tuple[str, BytesIO]:
    """텍스트를 렌더링해 (디스코드 이모지 이름, PNG 바이트) 튜플로 반환."""
    style = style or _load_style()
    emoji_name = romanize_hangul(text, style)

    canvas = style["canvas"]
    layout = style["layout"]
    paint = style["paint"]
    scale = canvas["scale"]
    width = canvas["width"]
    height = canvas["height"]
    font_path = ASSETS_DIR / Path(style["font"]["path"]).name

    image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _fit_font(draw, text, font_path, style)

    stroke_w = int(paint["stroke_width_px"] * scale)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width * scale - text_w) / 2 - bbox[0]
    y = (height * scale - text_h) / 2 - bbox[1] + int(layout["vertical_offset_px"] * scale)

    shadow_offset = int(paint["shadow_offset_px"] * scale)
    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=tuple(paint["shadow_rgba"]),
        stroke_width=stroke_w,
        stroke_fill=tuple(paint["shadow_rgba"]),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=tuple(paint["fill_rgba"]),
        stroke_width=stroke_w,
        stroke_fill=tuple(paint["stroke_rgba"]),
    )

    image = image.resize((width, height), Image.Resampling.LANCZOS)
    buf = BytesIO()
    image.save(buf, style["export"]["format"], optimize=style["export"]["optimize"])
    buf.seek(0)
    return emoji_name, buf
