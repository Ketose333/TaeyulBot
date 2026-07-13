from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

from resvg import render, usvg

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STYLE_PATH = ASSETS_DIR / "heart_style.json"
HEX_PATTERN = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _load_style() -> dict:
    with STYLE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_hex(hex_color: str) -> str:
    hex_color = hex_color.strip()
    if not HEX_PATTERN.match(hex_color):
        raise ValueError(f"'{hex_color}'는 올바른 hex 색상 형식이 아닙니다 (예: #112233).")
    return hex_color if hex_color.startswith("#") else f"#{hex_color}"


def render_heart(hex_color: str, style: dict | None = None) -> BytesIO:
    """지정한 hex 색상으로 하트 이모지를 렌더링해 PNG 바이트로 반환."""
    style = style or _load_style()
    hex_color = normalize_hex(hex_color)

    svg_path = ASSETS_DIR / Path(style["source_svg"]).name
    svg_template = svg_path.read_text(encoding="utf-8")
    svg = svg_template.replace(style["base_fill"], hex_color)

    opts = usvg.Options.default()
    tree = usvg.Tree.from_str(svg, opts)
    src_w, _ = tree.int_size()
    target_w = style["canvas"]["width"]
    scale = target_w / src_w

    png_bytes = render(tree, (scale, 0, 0, scale, 0, 0), bg_color=(0, 0, 0, 0))
    return BytesIO(png_bytes)
