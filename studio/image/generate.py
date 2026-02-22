#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.memory_auto_log import append_daily
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    for _p in _Path(__file__).resolve().parents:
        if (_p / 'utility').exists():
            sys.path.append(str(_p))
            break
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.memory_auto_log import append_daily

RULES_PATH = Path("/home/user/.openclaw/workspace/studio/image/rules/image_rules.md")

DEFAULT_TAEYUL_REF_IMAGE = "/home/user/.openclaw/workspace/avatars/taeyul.png"
DEFAULT_TAEYUL_2D_REF_IMAGE = "/home/user/.openclaw/media/avatars/taeyul2D.png"
BANNED_OUTPUT_ROOT = Path("/home/user/.openclaw/media/avatars").resolve()
SAFE_DEFAULT_OUTPUT_DIR = Path("/home/user/.openclaw/media/image").resolve()
LEGACY_IMAGES_DIR = Path("/home/user/.openclaw/media/images").resolve()

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
    return text or "image"


def _resolve_unique_name(out_dir: Path, name: str) -> str:
    p = Path(name)
    stem, suf = p.stem, p.suffix
    cand = out_dir / f"{stem}{suf}"
    i = 2
    while cand.exists():
        cand = out_dir / f"{stem}_{i}{suf}"
        i += 1
    return cand.name


def _purge_out_dir_matches(out_dir: Path, pattern: str) -> int:
    pat = (pattern or '').strip()
    if not pat:
        return 0
    # safety: only allow file-name glob within out_dir
    if '/' in pat or '\\' in pat:
        raise RuntimeError('purge pattern must be a filename glob (no path separators)')
    removed = 0
    for p in sorted(out_dir.glob(pat)):
        if p.is_file():
            p.unlink(missing_ok=True)
            removed += 1
    return removed

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

def _parse_kv_section(sections: dict[str, list[str]], name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in sections.get(name, []):
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        out[k.strip().lower()] = v.strip()
    return out

def _normalize_request_prompt(prompt: str) -> str:
    p = (prompt or "").strip()
    if not p:
        return "기본값 유지"

    sections = _parse_rules_sections()
    noise_terms = [x.strip().lower() for x in sections.get("REQUEST_NOISE_DROP", []) if x.strip()]
    noise_contains = [x.strip().lower() for x in sections.get("REQUEST_NOISE_CONTAINS", []) if x.strip()]

    rewrite_pairs: list[tuple[str, str]] = []
    for line in sections.get("REQUEST_CANONICAL_REWRITE", []):
        if "=>" not in line:
            continue
        src, dst = line.split("=>", 1)
        src = re.sub(r"\s+", " ", src.strip().lower())
        dst = dst.strip()
        if src and dst:
            rewrite_pairs.append((src, dst))

    # 쉼표/줄바꿈 단위로 잘라서 규칙 기반 노이즈 제거/정규화 적용
    tokens = [t.strip() for t in re.split(r"[\n,]", p) if t.strip()]

    normalized: list[str] = []
    seen_norm: set[str] = set()
    for t in tokens:
        norm = re.sub(r"\s+", " ", t.lower()).strip()
        if norm in noise_terms:
            continue

        replaced = t
        # contains 규칙은 토큰 전체를 버리지 않고 해당 문구만 제거한다.
        if noise_contains:
            for k in noise_contains:
                if not k:
                    continue
                replaced = re.sub(re.escape(k), " ", replaced, flags=re.IGNORECASE)
            replaced = re.sub(r"\s+", " ", replaced).strip(" ,.-:;")
            if not replaced:
                continue
            norm = re.sub(r"\s+", " ", replaced.lower()).strip()
        for src, dst in rewrite_pairs:
            if norm == src:
                replaced = dst
                norm = re.sub(r"\s+", " ", dst.lower()).strip()
                break

        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        normalized.append(replaced)

    joined = ", ".join(normalized).strip(" ,.-:;")
    return joined or "기본값 유지"

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

    if "nano-banana-pro-preview" in (model or ""):
        selected += sections.get("NANO_BANANA_PRO_GUARD", [])
        selected += sections.get("HARD_CASE_AVOIDANCE", [])

    if _is_outfit_only_request(prompt):
        selected += sections.get("OUTFIT_ONLY_LOCK", [])

    profile_key = (profile or "").strip().lower()
    profile_boost: list[str] = []
    if profile_key == "ketose":
        profile_boost = sections.get("REQUEST_PROFILE_BOOST_KETOSE", [])
    elif profile_key == "kwonjinhyuk":
        profile_boost = sections.get("REQUEST_PROFILE_BOOST_KWONJINHYUK", [])

    req = _normalize_request_prompt(prompt)

    # 과적합 방지: 규칙 기반으로 프로필 부스트 주입량을 제한한다.
    limits = _parse_kv_section(sections, "REQUEST_PROFILE_BOOST_LIMIT")
    try:
        default_limit = max(0, int(limits.get("default", "3")))
    except Exception:
        default_limit = 3
    try:
        rich_limit = max(0, int(limits.get("rich_prompt", "2")))
    except Exception:
        rich_limit = 2

    req_tokens = [t.strip() for t in re.split(r"[\n,]", req) if t.strip()]
    boost_limit = rich_limit if len(req_tokens) >= 3 else default_limit

    boost_items: list[str] = []
    if profile_boost and boost_limit > 0:
        seen = {re.sub(r"\s+", " ", t.lower()).strip() for t in req_tokens}
        for b in profile_boost:
            norm = re.sub(r"\s+", " ", b.lower()).strip()
            if norm in seen:
                continue
            boost_items.append(b)
            seen.add(norm)
            if len(boost_items) >= boost_limit:
                break

    if boost_items:
        req = req + "\n" + "\n".join(f"+ {x}" for x in boost_items)

    rules_text = _rules_to_text(selected)
    mode = "2D 모드" if allow_2d else "실사 모드"
    return (
        f"[규칙 소스: image_rules.md]\n{rules_text}\n\n"
        f"현재 생성 모드: {mode}\n"
        f"요청(프로필 반영):\n{req}"
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

    # compat alias auto-fix: ~/.openclaw/media/images -> ~/.openclaw/media/image
    if p == LEGACY_IMAGES_DIR:
        append_daily('- [경로 보정] gemini_image out-dir alias(images) -> media/image 자동 보정')
        p = SAFE_DEFAULT_OUTPUT_DIR

    try:
        p.relative_to(BANNED_OUTPUT_ROOT)
        raise RuntimeError('output path under ~/.openclaw/media/avatars is blocked; use ~/.openclaw/media/image instead')
    except ValueError:
        return p

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

    prompt_text = _avatar_lock_prompt(prompt, allow_2d=allow_2d, model=model, profile=profile) if (ref_image and lock_avatar) else _normalize_request_prompt(prompt)
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


def _ensure_true_png(path: Path) -> Path:
    """If file is not PNG bytes, transcode to a new *_converted.png file and return that path."""
    try:
        out = subprocess.run(["file", "--mime-type", "-b", str(path)], capture_output=True, text=True, check=False)
        mime = (out.stdout or '').strip().lower()
    except Exception:
        mime = ''
    if mime == 'image/png':
        return path

    converted = path.with_name(f"{path.stem}_converted.png")
    tmp = converted.with_suffix('.tmp.png')
    cmd = ['ffmpeg', '-y', '-i', str(path), str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or (not tmp.exists()):
        raise RuntimeError('PNG 변환 실패(ffmpeg)')
    tmp.replace(converted)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    return converted

def main() -> int:
    _force_utf8_stdio()
    load_env_prefer_dotenv()

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
    ap.add_argument("--profile", default="taeyul", choices=["taeyul","ketose","kwonjinhyuk","default"], help="Profile hint for rule selection")
    ap.add_argument("--aspect-ratio", default="1:1", help="Aspect ratio, e.g. 1:1, 4:5, 16:9, 9:16 (default: 1:1)")
    ap.add_argument("--purge-glob", default="", help="Delete existing files in out-dir matching this filename glob before save (e.g. 'ketose_selfie_clone_*.jpg')")
    args = ap.parse_args()

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("Missing GEMINI_API_KEY or GOOGLE_API_KEY", file=sys.stderr)
        return 2

    model = args.model if args.model.startswith("models/") else f"models/{args.model}"

    resolved_ref = "" if args.no_ref else _resolve_ref_image(args.ref_image, args.allow_2d)
    if resolved_ref:
        _validate_ref_image_path(resolved_ref)

    img_bytes = b""
    mime = "image/jpeg"
    last_err: Exception | None = None

    model_chain = [model]
    if model == "models/nano-banana-pro-preview":
        model_chain.append("models/gemini-2.5-flash-image")

    for mi, model_try in enumerate(model_chain):
        try:
            payload = call_generate(
                api_key,
                model_try,
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
        if mi < len(model_chain) - 1:
            print(f"fallback model: {model_chain[mi+1]}", file=sys.stderr)

    if last_err is not None:
        print(str(last_err), file=sys.stderr)
        return 1

    try:
        out_dir = _validate_out_dir_path(args.out_dir)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    if args.purge_glob.strip():
        try:
            removed = _purge_out_dir_matches(out_dir, args.purge_glob)
            if removed > 0:
                append_daily(f'- [이미지 정리] gemini_image purge-glob={args.purge_glob} removed={removed}')
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 1

    ext = ext_from_mime(mime)
    default_name = f"{slugify(args.prompt)[:60]}.{ext}"

    if args.name.strip():
        raw = args.name.strip()
        if "." not in Path(raw).name:
            raw = f"{raw}.{ext}"
        name = raw
    else:
        name = default_name

    name = _resolve_unique_name(out_dir, name)
    out = (out_dir / name).resolve()
    out.write_bytes(img_bytes)

    # 사용자가 PNG 경로를 기대할 때, 실제 바이너리도 PNG로 통일
    # (실제 변환이 일어난 경우에만 파일명을 *_converted.png로 변경)
    if out.suffix.lower() == '.png':
        out = _ensure_true_png(out)

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
