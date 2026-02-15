#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


def _wrap_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        box = draw.textbbox((0, 0), test, font=font)
        if (box[2] - box[0]) <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _rebalance_title_lines(lines: list[str]) -> list[str]:
    if len(lines) != 2:
        return lines

    a, b = lines[0].strip(), lines[1].strip()
    if not a or not b:
        return lines

    # 하단 캡션처럼 마지막 줄이 너무 짧지 않게 보정
    if len(b) >= max(4, int(len(a) * 0.45)):
        return [a, b]

    if " " in a:
        parts = a.split()
        if len(parts) >= 2:
            moved = parts[-1]
            na = " ".join(parts[:-1]).strip()
            nb = f"{moved} {b}".strip()
            if na and nb:
                return [na, nb]

    # 공백이 없거나 단어 이동 실패 시 문자 단위 보정
    if len(a) >= 4:
        moved = a[-2:]
        na = a[:-2].strip()
        nb = f"{moved}{b}".strip()
        if na and nb:
            return [na, nb]

    return [a, b]


def _fit_title(title: str, font_path: Path, draw: ImageDraw.ImageDraw, width: int, max_lines: int = 2) -> tuple[ImageFont.FreeTypeFont, str]:
    for size in range(104, 47, -2):
        f = ImageFont.truetype(str(font_path), size)
        lines = _wrap_to_width(title, f, width, draw)
        if len(lines) <= max_lines:
            lines = _rebalance_title_lines(lines)
            return f, "\n".join(lines)
    f = ImageFont.truetype(str(font_path), 48)
    lines = _wrap_to_width(title, f, width, draw)
    lines = _rebalance_title_lines(lines[:max_lines])
    return f, "\n".join(lines[:max_lines])


def _wrap_caption_chars(text: str, max_chars: int) -> str:
    """
    가급적 단어(어절) 단위로 줄바꿈을 수행하고,
    단어 하나가 max_chars보다 길 경우에만 중간 분할합니다.
    """
    if not text:
        return ""
    if max_chars <= 0:
        return text.replace("\n", " ").strip()
    
    # 이미 줄바꿈이 포함된 경우 그대로 반환하거나 처리 (중복 줄바꿈 방지)
    text = text.replace("\n", " ").strip()
    words = text.split()
    
    lines = []
    current_line = ""

    for word in words:
        # 1. 현재 줄이 비어있으면 일단 단어를 넣음
        if not current_line:
            # 단어 자체가 설정된 최대 길이보다 길 경우 강제 분할
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    lines.append(word[i:i + max_chars])
                # 마지막 조각은 다음 처리를 위해 current_line에 남겨둠 (보통 빈 문자열이 됨)
                last_chunk = lines.pop()
                current_line = last_chunk
            else:
                current_line = word
        else:
            # 2. 현재 줄에 다음 단어를 추가했을 때 길이를 계산 (공백 포함)
            test_line = f"{current_line} {word}"
            
            if len(test_line) <= max_chars:
                # 13자 이내라면 현재 줄에 추가
                current_line = test_line
            else:
                # 13자를 넘어가면 지금까지의 줄을 확정하고, 새 줄 시작
                lines.append(current_line)
                
                # 새 줄의 시작 단어가 너무 길 경우 강제 분할
                if len(word) > max_chars:
                    for i in range(0, len(word), max_chars):
                        lines.append(word[i:i + max_chars])
                    current_line = lines.pop()
                else:
                    current_line = word

    # 마지막에 남은 문구 추가
    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def _compress_caption_text(text: str) -> str:
    """간단한 축약: 의미는 유지하고 군더더기 조사/접속어를 줄인다."""
    t = text
    replacements = [
        ("그냥 ", ""),
        ("정말 ", ""),
        ("사실 ", ""),
        ("그리고 ", ""),
        ("그래서 ", ""),
        ("하는 거야", "함"),
        ("되는 거야", "됨"),
        ("할 수 있어", "가능"),
        ("할 수 있다", "가능"),
        ("입니다", "임"),
    ]
    for a,b in replacements:
        t=t.replace(a,b)
    t=t.replace("  "," ").strip()
    return t

def _rebalance_caption_lines(lines: list[str], max_chars: int, min_last: int = 5) -> list[str]:
    """마지막 줄이 너무 짧을 때 앞줄에서 단어를 넘겨 균등하게 보정."""
    if len(lines) < 2:
        return lines

    out = [x.strip() for x in lines if x.strip()]
    while len(out) >= 2 and len(out[-1]) < min_last:
        prev = out[-2]
        # 공백 단위 이동 우선
        if " " in prev:
            parts = prev.split()
            if len(parts) >= 2:
                moved = parts[-1]
                new_prev = " ".join(parts[:-1]).strip()
                new_last = f"{moved} {out[-1]}".strip()
                if new_prev and len(new_last) <= max_chars:
                    out[-2] = new_prev
                    out[-1] = new_last
                    continue
        # 공백이 없거나 이동 실패 시 문자 단위로 2자 이동
        if len(prev) > min_last + 2:
            moved = prev[-2:]
            new_prev = prev[:-2].strip()
            new_last = f"{moved}{out[-1]}".strip()
            if new_prev and len(new_last) <= max_chars:
                out[-2] = new_prev
                out[-1] = new_last
                continue
        break

    return out


def _fit_caption_without_ellipsis(text: str, max_chars: int, max_lines: int = 3) -> str:
    """
    목표: 화면을 벗어나지 않게 1~3줄 유지.
    초과 시 원문을 그대로 밀어넣지 않고, 의미 유지 축약본을 우선 사용.
    """
    clean = text.replace("\n", " ").strip()
    if not clean:
        return ""

    max_lines = max(1, min(3, max_lines))
    base_chars = max(1, max_chars)
    cap = base_chars * max_lines

    # 1) 원문 시도
    wrapped = _wrap_caption_chars(clean, base_chars)
    lines = [ln for ln in wrapped.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        lines = _rebalance_caption_lines(lines, base_chars)
        return "\n".join(lines)

    # 2) 축약본 시도
    compact = _compress_caption_text(clean)
    wrapped = _wrap_caption_chars(compact, base_chars)
    lines = [ln for ln in wrapped.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        lines = _rebalance_caption_lines(lines, base_chars)
        return "\n".join(lines)

    # 3) 마지막 안전장치: 단어 경계 기준으로 cap 내 절단(ellipsis 없음)
    trimmed = compact[:cap]
    cut = trimmed.rfind(" ")
    if cut >= max(1, int(cap * 0.6)):
        trimmed = trimmed[:cut]
    trimmed = trimmed.strip()
    wrapped = _wrap_caption_chars(trimmed, base_chars)
    lines = [ln for ln in wrapped.splitlines() if ln.strip()]
    lines = _rebalance_caption_lines(lines[:max_lines], base_chars)
    return "\n".join(lines[:max_lines])


def _tts_global_cache_dir(workspace: Path) -> Path:
    # workspace=/.../studio 기준, 상위 workspace 루트 아래 전역 TTS 캐시 사용
    root = workspace.parent if workspace.name == "studio" else workspace
    d = root / "media" / ".cache_tts_global"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tts_cache_key(voice: str, line: str) -> str:
    payload = json.dumps({"voice": voice, "line": line}, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def gen_tts_chunks(workspace: Path, lines: list[str], out_dir: Path, voice: str = "Charon", reuse: bool = True) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    global_cache = _tts_global_cache_dir(workspace)

    files: list[Path] = []
    in_run_cache: dict[str, Path] = {}

    for i, line in enumerate(lines, 1):
        name = f"c{i:02d}"
        out_wav = out_dir / f"{name}.wav"

        # 0) 기존 출력 재사용
        if reuse and out_wav.exists() and out_wav.stat().st_size > 0:
            files.append(out_wav)
            continue

        key = _tts_cache_key(voice, line)
        g_wav = global_cache / f"{key}.wav"

        # 1) 동일 실행 내 중복 라인 재사용
        if reuse and key in in_run_cache and in_run_cache[key].exists():
            shutil.copy2(in_run_cache[key], out_wav)
            files.append(out_wav)
            continue

        # 2) 전역 캐시 재사용 (쿼터 절약 핵심)
        if reuse and g_wav.exists() and g_wav.stat().st_size > 0:
            shutil.copy2(g_wav, out_wav)
            in_run_cache[key] = out_wav
            files.append(out_wav)
            continue

        # 3) 신규 생성
        cmd = [
            "python3",
            str(workspace / "gemini_tts.py"),
            line,
            "--voice",
            voice,
            "--out-dir",
            str(out_dir),
            "--name",
            name,
        ]
        run(cmd)
        if not out_wav.exists() or out_wav.stat().st_size == 0:
            raise RuntimeError(f"TTS chunk generation failed: {out_wav}")

        # 4) 전역 캐시에 저장
        try:
            shutil.copy2(out_wav, g_wav)
        except Exception:
            pass

        in_run_cache[key] = out_wav
        files.append(out_wav)

    return files


def gen_silent_chunks(lines: list[str], out_dir: Path, seconds: float = 1.4, sample_rate: int = 24000) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_frames = max(1, int(sample_rate * max(0.2, seconds)))
    # mono, 16-bit PCM silence
    silence = (b"\x00\x00" * n_frames)
    files: list[Path] = []
    for i, _line in enumerate(lines, 1):
        p = out_dir / f"c{i:02d}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(silence)
        files.append(p)
    return files


def stitch_wavs(wavs: list[Path], out_wav: Path) -> list[float]:
    params = None
    durations = []
    frames = []
    for p in wavs:
        with wave.open(str(p), "rb") as w:
            par = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            if params is None:
                params = par
            durations.append(w.getnframes() / w.getframerate())
            frames.append(w.readframes(w.getnframes()))

    with wave.open(str(out_wav), "wb") as o:
        o.setnchannels(params[0])
        o.setsampwidth(params[1])
        o.setframerate(params[2])
        for b in frames:
            o.writeframes(b)

    return durations


def fetch_youtube_assets(channel_id: str, out_dir: Path, count: int = 6, reuse: bool = True) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    vids: list[str] = []
    feed = requests.get(
        f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    ).text
    try:
        root = ET.fromstring(feed)
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        for e in root.findall("a:entry", ns)[:count]:
            node = e.find("yt:videoId", ns)
            if node is not None and node.text:
                vids.append(node.text)
    except ET.ParseError:
        # Fallback: scrape recent video ids from channel videos page when feed is blocked/invalid
        videos_html = requests.get(
            f"https://www.youtube.com/channel/{channel_id}/videos",
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        ).text
        vids = []
        for v in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', videos_html):
            if v not in vids:
                vids.append(v)
            if len(vids) >= count:
                break

    html = requests.get(
        f"https://www.youtube.com/channel/{channel_id}",
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    ).text
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    images = []
    if m:
        ch = out_dir / "channel.jpg"
        if (not reuse) or (not ch.exists()) or ch.stat().st_size == 0:
            ch.write_bytes(requests.get(m.group(1), timeout=30).content)
        images.append(ch)

    for v in vids:
        p = out_dir / f"{v}.jpg"
        if (not reuse) or (not p.exists()) or p.stat().st_size == 0:
            p.write_bytes(requests.get(f"https://i.ytimg.com/vi/{v}/hqdefault.jpg", timeout=30).content)
        images.append(p)

    return images


def fetch_extra_images(urls: list[str], out_dir: Path, reuse: bool = True) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for u in urls:
        try:
            ext = ".jpg"
            lu = u.lower()
            if ".png" in lu:
                ext = ".png"
            if ".webp" in lu:
                ext = ".webp"
            key = hashlib.sha1(u.encode("utf-8")).hexdigest()[:10]
            p = out_dir / f"web_{key}{ext}"
            if (not reuse) or (not p.exists()) or p.stat().st_size == 0:
                p.write_bytes(requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).content)

            # HTML/에러 페이지를 이미지로 오인하는 경우 방지
            try:
                with Image.open(p) as im:
                    im.verify()
            except Exception:
                try:
                    p.unlink()
                except Exception:
                    pass
                continue

            out.append(p)
        except Exception:
            continue
    return out


def render_video(
    images: list[Path],
    subtitle_lines: list[str],
    durations: list[float],
    stitched_wav: Path,
    out_mp4: Path,
    font_path: Path,
    title: str,
    subtitle: str,
    title_y: int,
    subtitle_y: int,
    caption_y: int,
    top_h: int = 600,
    bottom_h: int = 600,
    caption_font_path: Path | None = None,
    caption_y_offset: int = 0,
    subtitle_y_offset: int = 20,
    title_max_lines: int = 2,
    caption_max_chars: int = 18,
    caption_max_lines: int = 3,
    image_mode: str = "cover",
    image_pad: int = 20,
    auto_letterbox_layout: bool = True,
    image_y_offset: int = 0,
    title_y_nudge: int = 90,
):
    W, H = 1080, 1920
    mid_h = H - top_h - bottom_h

    fs = ImageFont.truetype(str(font_path), 60)
    cap_font = ImageFont.truetype(str(caption_font_path or font_path), 60)

    frame_dir = out_mp4.parent / f".{out_mp4.stem}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    list_txt = frame_dir / "list.txt"

    with list_txt.open("w", encoding="utf-8") as fl:
        last_frame = None

        # Letterbox-first layout: text positions are determined by letterbox, not image area.
        if auto_letterbox_layout:
            # Keep center alignment, but move text a bit lower while staying fully inside top letterbox.
            title_y = min(top_h - 120, int(top_h * 0.40) + title_y_nudge)
            subtitle_y = min(top_h - 56, int(top_h * 0.68) + 44)
            # Keep bottom captions close to image edge, but safely inside bottom letterbox.
            caption_y = min(H - 40, int((H - bottom_h) + max(54, min(92, bottom_h * 0.16)) + 20))

        for i, line in enumerate(subtitle_lines):
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            src = Image.open(images[i % len(images)]).convert("RGBA")
            safe_mid_h = max(120, mid_h - image_pad * 2 - abs(image_y_offset))
            safe_top = top_h + image_pad + image_y_offset
            if image_mode == "fit":
                ratio = min(W / src.width, safe_mid_h / src.height)
                rs = src.resize((int(src.width * ratio), int(src.height * ratio)))
                canvas.paste(rs, ((W - rs.width) // 2, safe_top + (safe_mid_h - rs.height) // 2))
            else:
                # cover: fill middle area fully (center-crop)
                ratio = max(W / src.width, safe_mid_h / src.height)
                rs = src.resize((int(src.width * ratio), int(src.height * ratio)))
                x = (rs.width - W) // 2
                y = (rs.height - safe_mid_h) // 2
                crop = rs.crop((x, y, x + W, y + safe_mid_h))
                canvas.paste(crop, (0, safe_top))

            d = ImageDraw.Draw(canvas)
            d.rectangle((0, 0, W, top_h), fill=(0, 0, 0, 255))
            d.rectangle((0, H - bottom_h, W, H), fill=(0, 0, 0, 255))

            title_font, title_wrapped = _fit_title(title, font_path, d, W - 120, max_lines=title_max_lines)
            d.multiline_text((W // 2, title_y), title_wrapped, font=title_font, fill=(255, 255, 255, 255), anchor="mm", align="center", spacing=8)
            d.text((W // 2, subtitle_y + subtitle_y_offset), subtitle, font=fs, fill=(255, 220, 40, 255), anchor="mm")

            caption_text = _wrap_caption_chars(line, caption_max_chars)
            caption_text = _fit_caption_without_ellipsis(caption_text, caption_max_chars, caption_max_lines)
            tx0, ty0, tx1, ty1 = d.multiline_textbbox((W // 2, caption_y + caption_y_offset), caption_text, font=cap_font, anchor="mm", align="center", spacing=8)
            pad_x, pad_y = 26, 18
            d.rounded_rectangle((tx0 - pad_x, ty0 - pad_y, tx1 + pad_x, ty1 + pad_y), radius=24, fill=(0, 0, 0, 170))
            d.multiline_text(
                (W // 2, caption_y + caption_y_offset),
                caption_text,
                font=cap_font,
                fill=(255, 255, 255, 255),
                anchor="mm",
                align="center",
                spacing=8,
            )

            fp = frame_dir / f"f{i:03d}.png"
            canvas.convert("RGB").save(fp)
            fl.write(f"file '{fp}'\n")
            fl.write(f"duration {durations[i]:.4f}\n")
            last_frame = fp

        fl.write(f"file '{last_frame}'\n")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    run(
        [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_txt),
            "-i",
            str(stitched_wav),
            "-shortest",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(out_mp4),
        ]
    )


def mix_with_bgm(tts_wav: Path, bgm_path: Path, out_wav: Path, tts_volume: float = 1.0, bgm_volume: float = 0.4) -> Path:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    run(
        [
            ff,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(bgm_path),
            "-i",
            str(tts_wav),
            "-filter_complex",
            f"[0:a]volume={bgm_volume}[bgm];[1:a]volume={tts_volume}[tts];[bgm][tts]amix=inputs=2:duration=shortest:dropout_transition=2[a]",
            "-map",
            "[a]",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(out_wav),
        ]
    )
    return out_wav


def main():
    p = argparse.ArgumentParser(description="Shorts pipeline (web images + chunk TTS + sync render)")
    p.add_argument("--workspace", default="/home/user/.openclaw/workspace/studio")
    p.add_argument("--channel-id", default="", help="YouTube channel id (comma-separated for multiple)")
    p.add_argument("--skip-youtube", action="store_true", help="skip YouTube image collection and use only extra-image-url/extra-image-file")
    p.add_argument("--extra-image-url", action="append", default=[], help="additional web image url (repeatable)")
    p.add_argument("--extra-image-file", action="append", default=[], help="additional local image file path (repeatable)")
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", default="", help="비우면 기존 기본값 유지")
    p.add_argument("--font", default="/home/user/.openclaw/workspace/fonts/SBAggroB.ttf")
    p.add_argument("--voice", default="Charon")
    p.add_argument("--out", required=True, help="output mp4 path")
    p.add_argument("--lines", required=True, help="text file: one TTS chunk per line")
    p.add_argument("--subs", default="", help="subtitle file: one subtitle chunk per line (omit => use --lines)")
    p.add_argument("--title-y", type=int, default=-1, help="title Y position (used when auto layout off)")
    p.add_argument("--subtitle-y", type=int, default=-1, help="subtitle Y position (used when auto layout off)")
    p.add_argument("--caption-y", type=int, default=-1, help="caption Y position (used when auto layout off)")
    p.add_argument("--caption-font", default="/home/user/.openclaw/workspace/fonts/BMDOHYEON.otf", help="caption-only font path")
    p.add_argument("--caption-y-offset", type=int, default=0, help="caption Y offset in px")
    p.add_argument("--subtitle-y-offset", type=int, default=48, help="subtitle Y offset in px")
    p.add_argument("--top-h", type=int, default=600, help="top letterbox height")
    p.add_argument("--bottom-h", type=int, default=600, help="bottom letterbox height")
    p.add_argument("--bgm", default="/home/user/.openclaw/workspace/media/bgm/bgm_full.mp3", help="background music path (empty to disable)")
    p.add_argument("--cache-key", default="", help="reuse key for web/chunks cache (e.g., dmusic)")
    p.add_argument("--no-reuse", action="store_true", help="disable cache reuse")
    p.add_argument("--no-tts", action="store_true", help="skip TTS generation and use silent placeholder chunks")
    p.add_argument("--tts-placeholder-seconds", type=float, default=5.0, help="per-line seconds for silent placeholder when --no-tts")
    p.add_argument("--cleanup-temp", action="store_true", help="remove temp frames/wav after render")
    p.add_argument("--keep-existing", action="store_true", help="keep existing output/cache artifacts (default: delete before run)")
    args = p.parse_args()

    ws = Path(args.workspace)
    out_mp4 = Path(args.out)
    lines = [x.strip() for x in Path(args.lines).read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.subs.strip():
        subs = [x.strip().replace("\\n", "\n") for x in Path(args.subs).read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        # --subs 생략 시 lines를 그대로 자막으로 사용 (중복 파일 생성 최소화)
        subs = list(lines)
    resolved_subtitle = args.subtitle.strip() or "핵심 요약"

    if len(lines) != len(subs):
        raise SystemExit("lines/subs line count mismatch")

    cache_key = args.cache_key.strip() or out_mp4.stem
    cache_root = out_mp4.parent / ".cache_shorts" / cache_key
    web_dir = cache_root / "web"
    chunk_dir = cache_root / "chunks"
    stitched = cache_root / "tts.wav"

    # 기본: 이전 산출물 정리 후 새로 생성
    frame_dir = out_mp4.parent / f".{out_mp4.stem}_frames"
    if not args.keep_existing:
        if out_mp4.exists():
            out_mp4.unlink()
        if frame_dir.exists():
            shutil.rmtree(frame_dir, ignore_errors=True)
        if cache_root.exists():
            shutil.rmtree(cache_root, ignore_errors=True)

    channel_ids = [x.strip() for x in args.channel_id.split(",") if x.strip()]
    images: list[Path] = []
    per = max(3, 8 // max(1, len(channel_ids)))
    reuse = not args.no_reuse
    if not args.skip_youtube:
        for cid in channel_ids:
            images.extend(fetch_youtube_assets(cid, web_dir / cid, count=per, reuse=reuse))
    if args.extra_image_url:
        images.extend(fetch_extra_images(args.extra_image_url, web_dir / "web", reuse=reuse))
    if args.extra_image_file:
        seen_local: set[Path] = set()
        for fp in args.extra_image_file:
            pth = Path(fp)
            if pth.exists() and pth.is_file() and pth not in seen_local:
                images.append(pth)
                seen_local.add(pth)
    if not images:
        raise SystemExit("no images collected from youtube/web/local")

    if args.no_tts:
        wavs = gen_silent_chunks(lines, chunk_dir, seconds=args.tts_placeholder_seconds)
    else:
        wavs = gen_tts_chunks(ws, lines, chunk_dir, voice=args.voice, reuse=reuse)
    durations = stitch_wavs(wavs, stitched)

    final_audio = stitched
    if args.bgm.strip():
        mixed = cache_root / "mix.wav"
        tts_vol = 0.0 if args.no_tts else 1.0
        final_audio = mix_with_bgm(
            stitched,
            Path(args.bgm),
            mixed,
            tts_volume=tts_vol,
            bgm_volume=0.4,
        )

    render_video(
        images=images,
        subtitle_lines=subs,
        durations=durations,
        stitched_wav=final_audio,
        out_mp4=out_mp4,
        font_path=Path(args.font),
        title=args.title,
        subtitle=resolved_subtitle,
        title_y=args.title_y,
        subtitle_y=args.subtitle_y,
        caption_y=args.caption_y,
        caption_font_path=Path(args.caption_font) if args.caption_font else None,
        caption_y_offset=args.caption_y_offset,
        subtitle_y_offset=args.subtitle_y_offset,
        title_max_lines=2,
        caption_max_chars=18,
        caption_max_lines=3,
        top_h=args.top_h,
        bottom_h=args.bottom_h,
        image_mode="cover",
        image_pad=20,
        auto_letterbox_layout=True,
        image_y_offset=0,
        title_y_nudge=90,
    )

    if args.cleanup_temp:
        frame_dir = out_mp4.parent / f".{out_mp4.stem}_frames"
        if frame_dir.exists():
            shutil.rmtree(frame_dir, ignore_errors=True)

    print(out_mp4)


if __name__ == "__main__":
    main()
