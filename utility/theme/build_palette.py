#!/usr/bin/env python3
"""
Build RGB fallback palette.css from palette.oklch.css.

Usage:
  python3 utility/theme/build_palette.py <input_oklch_css> <output_css>
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

HEADER = """/* AUTO-GENERATED from palette.oklch.css by utility/theme/build_palette.py */
/* Single source of truth: palette.oklch.css */

"""

OKLCH_RE = re.compile(r"oklch\(([^()]+)\)")


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def _srgb_encode(linear: float) -> float:
    linear = _clamp01(linear)
    if linear <= 0.0031308:
        return 12.92 * linear
    return 1.055 * (linear ** (1.0 / 2.4)) - 0.055


def oklch_to_rgb_string(inner: str) -> str:
    # format: "L C h" or "L C h / a"
    part = inner.strip()
    alpha = None
    if "/" in part:
        left, right = part.split("/", 1)
        part = left.strip()
        alpha = right.strip()

    tokens = [t for t in part.split() if t]
    if len(tokens) != 3:
        # keep original if unexpected
        return f"oklch({inner})"

    L_tok, C_tok, h_tok = tokens

    try:
        L = float(L_tok[:-1]) / 100.0 if L_tok.endswith("%") else float(L_tok)
        C = float(C_tok)
        h = float(h_tok)
    except ValueError:
        return f"oklch({inner})"

    hr = math.radians(h)
    a_ = C * math.cos(hr)
    b_ = C * math.sin(hr)

    l_ = L + 0.3963377774 * a_ + 0.2158037573 * b_
    m_ = L - 0.1055613458 * a_ - 0.0638541728 * b_
    s_ = L - 0.0894841775 * a_ - 1.2914855480 * b_

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r_lin = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g_lin = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_lin = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    r = round(_srgb_encode(r_lin) * 255)
    g = round(_srgb_encode(g_lin) * 255)
    b = round(_srgb_encode(b_lin) * 255)

    if alpha is not None:
        return f"rgb({r} {g} {b} / {alpha})"
    return f"rgb({r} {g} {b})"


def build(input_path: Path, output_path: Path) -> None:
    src = input_path.read_text(encoding="utf-8")
    converted = OKLCH_RE.sub(lambda m: oklch_to_rgb_string(m.group(1)), src)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(HEADER + converted, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        # default for current workspace layout
        script_dir = Path(__file__).resolve().parent
        workspace_root = script_dir.parent.parent
        input_path = (workspace_root / "tcg" / "vercel" / "public" / "palette.oklch.css").resolve()
        output_path = (workspace_root / "tcg" / "vercel" / "public" / "palette.css").resolve()
    elif len(argv) == 3:
        input_path = Path(argv[1]).expanduser().resolve()
        output_path = Path(argv[2]).expanduser().resolve()
    else:
        print("Usage: python3 utility/theme/build_palette.py <input_oklch_css> <output_css>")
        print("   or: python3 utility/theme/build_palette.py")
        return 2

    if not input_path.exists():
        print(f"Input not found: {input_path}")
        return 2

    build(input_path, output_path)
    print(f"Built: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
