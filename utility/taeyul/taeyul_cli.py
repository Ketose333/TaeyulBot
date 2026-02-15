#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

STUDIO = Path("/home/user/.openclaw/workspace/studio")
DEFAULT_TAEYUL_REF_IMAGE = "/home/user/.openclaw/workspace/avatars/taeyul.png"


def _run(script: str, *args: str) -> int:
    return subprocess.run(["python3", str(STUDIO / script), *args]).returncode


def _append_indexed_name(name: str, idx: int, count: int) -> str:
    if count <= 1:
        return name
    p = Path(name)
    stem = p.stem or name
    suffix = p.suffix
    return f"{stem}_{idx:02d}{suffix}"


def main() -> int:
    p = argparse.ArgumentParser(description="taeyul internal compact cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_tts = sub.add_parser("tts")
    p_tts.add_argument("text")
    p_tts.add_argument("--voice", default="Fenrir")
    p_tts.add_argument("--out-dir", default="./output")
    p_tts.add_argument("--name", default="")
    p_tts.add_argument("--emit-media", action="store_true")

    p_img = sub.add_parser("image")
    p_img.add_argument("prompt")
    p_img.add_argument("--model", default="nano-banana-pro-preview")
    p_img.add_argument("--out-dir", default="/home/user/.openclaw/media/image")
    p_img.add_argument("--name", default="")
    p_img.add_argument("--ref-image", default=DEFAULT_TAEYUL_REF_IMAGE)
    p_img.add_argument("--no-ref", action="store_true")
    p_img.add_argument("--no-avatar-lock", action="store_true")
    p_img.add_argument("--allow-2d", action="store_true")
    p_img.add_argument("--emit-media", action="store_true")
    p_img.add_argument("--keep-existing", action="store_true")
    p_img.add_argument("--count", type=int, default=1, help="generate N images")
    p_img.add_argument("--profile", default="taeyul", choices=["taeyul", "ketose", "kwonjinhyuk", "default"], help="identity profile hint")
    p_img.add_argument("--aspect-ratio", default="")
    p_img.add_argument("--max-attempts", type=int, default=3)

    p_veo = sub.add_parser("veo")
    p_veo.add_argument("prompt")
    p_veo.add_argument("--model", default="models/veo-3.1-generate-preview")
    p_veo.add_argument("--out-dir", default="/home/user/.openclaw/workspace/media/video")
    p_veo.add_argument("--name", default="veo_clip")
    p_veo.add_argument("--poll-seconds", type=int, default=180)

    p_shorts = sub.add_parser("shorts")
    for req in ("--channel-id", "--title", "--lines", "--subs", "--out"):
        p_shorts.add_argument(req, required=True)
    p_shorts.add_argument("--subtitle", default="")
    p_shorts.add_argument("--title-y", required=True, type=int)
    p_shorts.add_argument("--subtitle-y", required=True, type=int)
    p_shorts.add_argument("--caption-y", required=True, type=int)
    p_shorts.add_argument("--voice", default="Charon")
    p_shorts.add_argument("--font", default="/home/user/.openclaw/workspace/fonts/SBAggroB.ttf")
    p_shorts.add_argument("--caption-font", default="")
    p_shorts.add_argument("--caption-y-offset", type=int, default=0)

    a = p.parse_args()

    if a.cmd == "tts":
        args = [a.text, "--voice", a.voice, "--out-dir", a.out_dir]
        if a.name:
            args += ["--name", a.name]
        if a.emit_media:
            args += ["--emit-media"]
        return _run("gemini_tts.py", *args)

    if a.cmd == "image":
        count = max(1, int(a.count or 1))
        rc = 0
        for i in range(1, count + 1):
            args = [a.prompt, "--model", a.model, "--out-dir", a.out_dir, "--profile", a.profile, "--max-attempts", str(a.max_attempts)]
            if a.aspect_ratio:
                args += ["--aspect-ratio", a.aspect_ratio]
            if a.name:
                args += ["--name", _append_indexed_name(a.name, i, count)]
            if a.no_ref:
                args += ["--no-ref"]
            elif a.ref_image:
                args += ["--ref-image", a.ref_image]
            if a.no_avatar_lock:
                args += ["--no-avatar-lock"]
            if a.allow_2d:
                args += ["--allow-2d"]
            if a.emit_media:
                args += ["--emit-media"]
            if a.keep_existing:
                args += ["--keep-existing"]
            one = _run("gemini_image.py", *args)
            if one != 0:
                rc = one
                break
        return rc

    if a.cmd == "veo":
        return _run("gemini_veo.py", a.prompt, "--model", a.model, "--out-dir", a.out_dir, "--name", a.name, "--poll-seconds", str(a.poll_seconds))

    subtitle = a.subtitle.strip() or "핵심 요약"
    args = [
        "--workspace", str(STUDIO),
        "--channel-id", a.channel_id,
        "--title", a.title,
        "--subtitle", subtitle,
        "--font", a.font,
        "--voice", a.voice,
        "--out", a.out,
        "--lines", a.lines,
        "--subs", a.subs,
        "--title-y", str(a.title_y),
        "--subtitle-y", str(a.subtitle_y),
        "--caption-y", str(a.caption_y),
        "--caption-y-offset", str(a.caption_y_offset),
    ]
    if a.caption_font:
        args += ["--caption-font", a.caption_font]
    return _run("shorts_pipeline.py", *args)


if __name__ == "__main__":
    raise SystemExit(main())
