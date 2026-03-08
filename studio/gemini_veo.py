#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.generation_defaults import (
        DEFAULT_VEO_ASPECT_RATIO,
        DEFAULT_VEO_MODEL,
        MEDIA_VIDEO_DIR,
        WORKSPACE_ROOT,
    )
    from utility.common.path_policy import resolve_out_dir
    from utility.common.filename_policy import resolve_unique_path
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path
    sys.path.append(str(_Path(__file__).resolve().parent.parent))
    from utility.common.bootstrap import ensure_utility_imports
    ensure_utility_imports(__file__)
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.common.generation_defaults import (
        DEFAULT_VEO_ASPECT_RATIO,
        DEFAULT_VEO_MODEL,
        MEDIA_VIDEO_DIR,
        WORKSPACE_ROOT,
    )
    from utility.common.path_policy import resolve_out_dir
    from utility.common.filename_policy import resolve_unique_path

RULES_PATH = (WORKSPACE_ROOT / 'studio' / 'image' / 'rules' / 'image_rules.md').resolve()
SAFE_DEFAULT_OUTPUT_DIR = MEDIA_VIDEO_DIR
def resolve_unique_video_path(out_dir: Path, base_name: str) -> Path:
    return resolve_unique_path(out_dir, base_name, '.mp4', fallback='video')


def _resolve_out_dir(out_dir: str) -> Path:
    return resolve_out_dir(out_dir, SAFE_DEFAULT_OUTPUT_DIR)


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


def _build_locked_prompt(prompt: str) -> str:
    sections = _parse_rules_sections()
    selected: list[str] = []
    selected += sections.get("COMMON_IDENTITY_LOCK", [])
    selected += sections.get("REAL_STYLE_GUARD", [])
    selected += sections.get("HARD_CASE_AVOIDANCE", [])
    if _is_outfit_only_request(prompt):
        selected += sections.get("OUTFIT_ONLY_LOCK", [])

    rules_text = _rules_to_text(selected)
    return (
        f"[규칙 소스: image_rules.md]\n{rules_text}\n\n"
        f"요청: {prompt}"
    )


def post_json(url: str, body: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def get_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"x-goog-api-key": api_key}, method="GET")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def extract_video_bytes(payload: dict) -> bytes | None:
    cands = payload.get("response", {}).get("candidates", []) or payload.get("candidates", [])
    for c in cands:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    return None


def extract_video_uri(payload: dict) -> str | None:
    resp = payload.get("response", {})
    gen = resp.get("generateVideoResponse", {})
    samples = gen.get("generatedSamples", [])
    for s in samples:
        uri = s.get("video", {}).get("uri")
        if uri:
            return uri
    return None


def download_bytes(url: str, api_key: str) -> bytes:
    req = urllib.request.Request(url, headers={"x-goog-api-key": api_key}, method="GET")
    with urllib.request.urlopen(req, timeout=240) as r:
        return r.read()


def main() -> int:
    load_env_prefer_dotenv()
    ap = argparse.ArgumentParser(description="Generate video with Gemini Veo (no-ref workflow)")
    ap.add_argument("prompt")
    ap.add_argument("--model", default=DEFAULT_VEO_MODEL)
    ap.add_argument("--out-dir", default=str(SAFE_DEFAULT_OUTPUT_DIR))
    ap.add_argument("--name", default="", help="Output filename stem (optional)")
    ap.add_argument("--poll-seconds", type=int, default=180)
    ap.add_argument("--aspect-ratio", default=DEFAULT_VEO_ASPECT_RATIO, help="Aspect ratio, e.g. 1:1, 9:16, 16:9 (default: 1:1)")
    ap.add_argument("--emit-media", action="store_true", help="Print MEDIA:relative_path")
    args = ap.parse_args()

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("Missing GEMINI_API_KEY or GOOGLE_API_KEY", file=sys.stderr)
        return 2

    prompt = _build_locked_prompt(args.prompt)
    instance: dict = {"prompt": prompt}

    start_url = f"https://generativelanguage.googleapis.com/v1beta/{args.model}:predictLongRunning"
    body = {
        "instances": [instance],
        "parameters": {"aspectRatio": (args.aspect_ratio or DEFAULT_VEO_ASPECT_RATIO)},
    }

    try:
        start = post_json(start_url, body, api_key)
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", errors="replace")
        print(f"Veo start failed ({e.code}): {payload}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Veo start failed: {e}", file=sys.stderr)
        return 1

    video_bytes = extract_video_bytes(start)
    if not video_bytes:
        uri = extract_video_uri(start)
        if uri:
            video_bytes = download_bytes(uri, api_key)
    if video_bytes:
        out = _resolve_out_dir(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        name_base = (args.name or "").strip() or args.prompt
        path = resolve_unique_video_path(out, name_base)
        path.write_bytes(video_bytes)
        cwd = Path.cwd().resolve()
        try:
            rel = path.resolve().relative_to(cwd)
            media_path = f"./{rel.as_posix()}"
        except ValueError:
            media_path = path.resolve().as_posix()
        if args.emit_media:
            print(f"MEDIA:{media_path}")
        else:
            print(f"VIDEO:{media_path}")
        return 0

    op_name = start.get("name")
    if not op_name:
        print(f"Veo response did not include operation/video payload: {json.dumps(start, ensure_ascii=False)[:1000]}", file=sys.stderr)
        return 1

    deadline = time.time() + args.poll_seconds
    last = None
    while time.time() < deadline:
        try:
            st = get_json(f"https://generativelanguage.googleapis.com/v1beta/{op_name}", api_key)
        except Exception as e:
            last = {"error": str(e)}
            time.sleep(3)
            continue
        last = st
        if st.get("done"):
            if "error" in st:
                print(f"Veo operation error: {json.dumps(st['error'], ensure_ascii=False)}", file=sys.stderr)
                return 1
            video_bytes = extract_video_bytes(st)
            if not video_bytes:
                uri = extract_video_uri(st)
                if uri:
                    video_bytes = download_bytes(uri, api_key)
            if not video_bytes:
                print(f"Veo done but no inline video bytes. Raw: {json.dumps(st, ensure_ascii=False)[:1500]}", file=sys.stderr)
                return 1
            out = _resolve_out_dir(args.out_dir)
            out.mkdir(parents=True, exist_ok=True)
            name_base = (args.name or "").strip() or args.prompt
            path = resolve_unique_video_path(out, name_base)
            path.write_bytes(video_bytes)
            cwd = Path.cwd().resolve()
            try:
                rel = path.resolve().relative_to(cwd)
                media_path = f"./{rel.as_posix()}"
            except ValueError:
                media_path = path.resolve().as_posix()
            if args.emit_media:
                print(f"MEDIA:{media_path}")
            else:
                print(f"VIDEO:{media_path}")
            return 0
        time.sleep(4)

    print(f"Veo polling timed out. Last: {json.dumps(last, ensure_ascii=False)[:1200]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
