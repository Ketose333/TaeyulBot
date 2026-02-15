#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

RULES_PATH = Path("/home/user/.openclaw/workspace/studio/IMAGE_RULES.md")

DEFAULT_TAEYUL_REF_IMAGE = "/home/user/.openclaw/workspace/avatars/taeyul.png"
DEFAULT_TAEYUL_2D_REF_IMAGE = "/home/user/.openclaw/media/avatars/taeyul2D.png"
BANNED_OUTPUT_ROOT = Path("/home/user/.openclaw/media/avatars").resolve()
SAFE_DEFAULT_OUTPUT_DIR = Path("/home/user/.openclaw/media/image").resolve()


def _force_utf8_stdio() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "image"




def _parse_rules_sections() -> dict[str, list[str]]:
    try:
        text = RULES_PATH.read_text(encoding="utf-8")
    except Exception:
        return {}

    sections: dict[str, list[str]] = {}
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current and line.startswith("- "):
            sections[current].append(line[2:].strip())
    return sections


def _is_outfit_only_request(prompt: str) -> bool:
    p = (prompt or "").lower()
    keys = ["의상", "옷", "outfit", "costume", "wardrobe", "착장"]
    return any(k in p for k in keys)


def _rules_to_text(lines: list[str]) -> str:
    return "\n".join(f"- {x}" for x in lines if x)


def _normalize_request_prompt(prompt: str) -> str:
    p = (prompt or "").strip()
    for pref in ("한태율 실사 인물 사진", "한태율 실사 사진", "한태율 실사"):
        if p.startswith(pref):
            p = p[len(pref):].lstrip(" ,.-:;	")
            break
    return p or "기본값 유지"


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _avatar_lock_prompt(prompt: str, allow_2d: bool = False, model: str = "", profile: str = "taeyul") -> str:
    sections = _parse_rules_sections()

    selected: list[str] = []
    selected += sections.get("COMMON_IDENTITY_LOCK", [])
    selected += sections.get("REF_IMAGE_POLICY", [])

    if allow_2d:
        selected += sections.get("TWO_D_STYLE_GUARD", [])
    else:
        selected += sections.get("REAL_STYLE_GUARD", [])

    # baseline rules that should apply regardless of model family
    selected += sections.get("FRAMING_AND_POSE_BASELINE", [])
    selected += sections.get("BACKGROUND_QUALITY_BASELINE", [])
    selected += sections.get("PROMPT_MINIMALISM", [])
    selected += sections.get("PROMPT_INPUT_POLICY", [])

    if "nano-banana-pro-preview" in (model or ""):
        selected += sections.get("NANO_BANANA_PRO_GUARD", [])
        selected += sections.get("HARD_CASE_AVOIDANCE", [])

    if _is_outfit_only_request(prompt):
        selected += sections.get("OUTFIT_ONLY_LOCK", [])

    profile_key = (profile or "").strip().lower()
    if profile_key == "ketose":
        selected += sections.get("USER_VISUAL_HINT_KETOSE", [])
    elif profile_key == "kwonjinhyuk":
        selected += sections.get("USER_VISUAL_HINT_KWONJINHYUK", [])

    req = _normalize_request_prompt(prompt)
    rules_text = _rules_to_text(selected)
    mode = "2D 모드" if allow_2d else "실사 모드"
    return (
        f"[규칙 소스: IMAGE_RULES.md]\n{rules_text}\n\n"
        f"현재 생성 모드: {mode}\n"
        f"요청: {req}"
    )




def _resolve_ref_image(ref_image: str, allow_2d: bool) -> str:
    ref = (ref_image or "").strip()
    if not ref:
        ref = DEFAULT_TAEYUL_REF_IMAGE

    # If caller uses default avatar ref and requests 2D mode, switch to dedicated 2D ref.
    if allow_2d and ref == DEFAULT_TAEYUL_REF_IMAGE:
        p2d = Path(DEFAULT_TAEYUL_2D_REF_IMAGE).expanduser()
        if p2d.exists() and p2d.is_file():
            return str(p2d)
    return ref



def _validate_ref_image_path(ref_image: str) -> None:
    p = Path((ref_image or '').strip()).expanduser().resolve()
    if not p:
        return
    # Prevent identity drift from chaining generated outputs as new references.
    banned_root = Path('/home/user/.openclaw/media/image').resolve()
    try:
        p.relative_to(banned_root)
        raise RuntimeError('generated image under ~/.openclaw/media/image cannot be used as --ref-image; use avatar/original reference instead')
    except ValueError:
        return


def _validate_out_dir_path(out_dir: str) -> Path:
    p = Path((out_dir or '').strip() or str(SAFE_DEFAULT_OUTPUT_DIR)).expanduser().resolve()
    try:
        p.relative_to(BANNED_OUTPUT_ROOT)
        raise RuntimeError('output path under ~/.openclaw/media/avatars is blocked; use ~/.openclaw/media/image instead')
    except ValueError:
        return p


def _purge_media_image_dir_if_needed(out_dir: Path, keep_existing: bool) -> None:
    if keep_existing:
        return
    if out_dir != SAFE_DEFAULT_OUTPUT_DIR:
        return
    if not out_dir.exists():
        return
    for child in out_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception:
            continue

def call_generate(
    api_key: str,
    model: str,
    prompt: str,
    ref_image: str = "",
    lock_avatar: bool = True,
    allow_2d: bool = False,
    profile: str = "taeyul",
    aspect_ratio: str = "",
) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"

    prompt_text = _avatar_lock_prompt(prompt, allow_2d=allow_2d, model=model, profile=profile) if (ref_image and lock_avatar) else prompt
    parts = []

    if ref_image:
        p = Path(ref_image).expanduser().resolve()
        if not p.exists() or not p.is_file():
            raise RuntimeError(f"reference image not found: {p}")
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        parts.append(
            {
                "inline_data": {
                    "mime_type": _guess_mime(p),
                    "data": b64,
                }
            }
        )

    parts.append({"text": prompt_text})

    gen_cfg: dict = {"responseModalities": ["TEXT", "IMAGE"]}
    ar = (aspect_ratio or "").strip()
    if ar:
        gen_cfg["imageConfig"] = {"aspectRatio": ar}

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": gen_cfg,
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
        raise RuntimeError(f"Gemini image generation failed ({e.code}): {payload}") from e


def extract_image(payload: dict) -> tuple[bytes, str]:
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


def main() -> int:
    _force_utf8_stdio()

    ap = argparse.ArgumentParser(description="Generate image using Gemini API (UTF-8 safe)")
    ap.add_argument("prompt", help="Image prompt")
    ap.add_argument("--model", default="nano-banana-pro-preview", help="Model id (without models/ prefix)")
    ap.add_argument("--out-dir", default=str(SAFE_DEFAULT_OUTPUT_DIR), help="Output directory")
    ap.add_argument("--name", default="", help="Output filename (optional)")
    ap.add_argument("--ref-image", default=DEFAULT_TAEYUL_REF_IMAGE, help="Reference image path for identity lock (default: taeyul avatar)")
    ap.add_argument("--no-ref", action="store_true", help="Disable reference image entirely")
    ap.add_argument("--no-avatar-lock", action="store_true", help="Disable strict same-identity prompt lock when --ref-image is used")
    ap.add_argument("--allow-2d", action="store_true", help="Allow non-photorealistic 2D/cartoon style (auto-uses taeyul2D ref when default ref is used)")
    ap.add_argument("--emit-media", action="store_true", help="Print MEDIA:relative_path for direct chat attachment")
    ap.add_argument("--keep-existing", action="store_true", help="Keep existing files in output directory (default: purge ~/.openclaw/media/image before save)")
    ap.add_argument("--profile", default="taeyul", choices=["taeyul","ketose","kwonjinhyuk","default"], help="Profile hint for rule selection")
    ap.add_argument("--aspect-ratio", default="", help="Aspect ratio, e.g. 1:1, 4:5, 16:9, 9:16")
    ap.add_argument("--max-attempts", type=int, default=3, help="Max generation attempts on failure (default: 3)")
    args = ap.parse_args()

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("Missing GEMINI_API_KEY or GOOGLE_API_KEY", file=sys.stderr)
        return 2

    model = args.model if args.model.startswith("models/") else f"models/{args.model}"

    resolved_ref = "" if args.no_ref else _resolve_ref_image(args.ref_image, args.allow_2d)
    if resolved_ref:
        _validate_ref_image_path(resolved_ref)

    max_attempts = max(1, int(args.max_attempts or 1))
    img_bytes = b""
    mime = "image/jpeg"
    last_err: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            payload = call_generate(
                api_key,
                model,
                args.prompt,
                ref_image=resolved_ref,
                lock_avatar=not args.no_avatar_lock,
                allow_2d=args.allow_2d,
                profile=args.profile,
                aspect_ratio=args.aspect_ratio,
            )
            img_bytes, mime = extract_image(payload)
            last_err = None
            break
        except Exception as e:
            last_err = e
            if attempt < max_attempts:
                print(f"retry {attempt}/{max_attempts-1}: {e}", file=sys.stderr)
                continue

    if last_err is not None:
        print(str(last_err), file=sys.stderr)
        return 1

    try:
        out_dir = _validate_out_dir_path(args.out_dir)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    _purge_media_image_dir_if_needed(out_dir, args.keep_existing)

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = ext_from_mime(mime)
    default_name = f"gemini-{slugify(args.prompt)[:40]}-{ts}.{ext}"

    if args.name.strip():
        raw = args.name.strip()
        if "." not in Path(raw).name:
            raw = f"{raw}.{ext}"
        name = raw
    else:
        name = default_name

    out = (out_dir / name).resolve()
    out.write_bytes(img_bytes)

    cwd = Path.cwd().resolve()
    try:
        rel = out.relative_to(cwd)
        media_path = f"./{rel.as_posix()}"
    except ValueError:
        media_path = out.as_posix()

    if args.emit_media:
        print(f"MEDIA:{media_path}")
    else:
        print(f"IMAGE:{media_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
