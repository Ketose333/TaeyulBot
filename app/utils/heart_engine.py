from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STYLE_PATH = ASSETS_DIR / "heart_style.json"
BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
HEX_PATTERN = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _resvg_binary() -> Path:
    if platform.system() == "Windows":
        path = BIN_DIR / "win64" / "resvg.exe"
    else:
        path = BIN_DIR / "linux64" / "resvg"
    if not path.exists():
        raise RuntimeError(f"resvg 바이너리를 찾을 수 없습니다: {path}")
    if platform.system() != "Windows" and not os.access(path, os.X_OK):
        os.chmod(path, 0o755)
    return path


def _load_style() -> dict:
    with STYLE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_hex(hex_color: str) -> str:
    hex_color = hex_color.strip()
    if not HEX_PATTERN.match(hex_color):
        raise ValueError(f"'{hex_color}'는 올바른 hex 색상 형식이 아닙니다 (예: #112233).")
    return hex_color if hex_color.startswith("#") else f"#{hex_color}"


def render_heart(hex_color: str, style: dict | None = None) -> BytesIO:
    """지정한 hex 색상으로 하트 이모지를 렌더링해 PNG 바이트로 반환.

    렌더링은 resvg 공식 CLI 바이너리(app/bin/)로 수행한다. PyPI의 resvg
    파이썬 바인딩(v0.2.0)은 transform 배율에 따라 빈 이미지를 반환하거나
    도형이 잘리는 버그가 확인되어 사용하지 않는다.
    """
    style = style or _load_style()
    hex_color = normalize_hex(hex_color)

    svg_path = ASSETS_DIR / Path(style["source_svg"]).name
    svg_template = svg_path.read_text(encoding="utf-8")
    svg = svg_template.replace(style["base_fill"], hex_color)

    binary = _resvg_binary()
    width = style["canvas"]["width"]
    height = style["canvas"]["height"]

    with tempfile.TemporaryDirectory() as tmp:
        svg_path_tmp = Path(tmp) / "heart.svg"
        png_path_tmp = Path(tmp) / "heart.png"
        svg_path_tmp.write_text(svg, encoding="utf-8")

        result = subprocess.run(
            [str(binary), "-w", str(width), "-h", str(height),
             "--background", "transparent", str(svg_path_tmp), str(png_path_tmp)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"resvg 렌더링 실패: {result.stderr.strip()}")

        return BytesIO(png_path_tmp.read_bytes())
