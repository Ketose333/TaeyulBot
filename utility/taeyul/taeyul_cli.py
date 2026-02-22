#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from utility.common.memory_auto_log import append_retro, maybe_log_feedback
except ModuleNotFoundError:
    append_retro = None  # type: ignore
    maybe_log_feedback = None  # type: ignore

for _p in Path(__file__).resolve().parents:
    if (_p / "utility").exists():
        if str(_p) not in sys.path:
            sys.path.append(str(_p))
        break

if append_retro is None or maybe_log_feedback is None:
    from utility.common.memory_auto_log import append_retro, maybe_log_feedback

STUDIO = Path("/home/user/.openclaw/workspace/studio")
IMAGE_DIR = STUDIO / "image"
SHORTS_DIR = STUDIO / "shorts"
DEFAULT_TAEYUL_REF_IMAGE = "/home/user/.openclaw/workspace/avatars/taeyul.png"


def _run(script: str, *args: str) -> int:
    script_map = {
        "gemini_tts.py": STUDIO / "gemini_tts.py",
        "gemini_veo.py": STUDIO / "gemini_veo.py",
        "generate.py": IMAGE_DIR / "generate.py",
        "pipeline.py": SHORTS_DIR / "pipeline.py",
    }
    target = script_map.get(script)
    if target is None:
        target = STUDIO / script
    return subprocess.run(["python3", str(target), *args]).returncode


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
    p_tts.add_argument("--out-dir", default="/home/user/.openclaw/media/audio")
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
    p_img.add_argument("--count", type=int, default=1, help="generate N images")
    p_img.add_argument("--profile", default="taeyul", choices=["taeyul", "ketose", "kwonjinhyuk", "default"], help="identity profile hint")
    p_img.add_argument("--aspect-ratio", default="")

    p_veo = sub.add_parser("veo")
    p_veo.add_argument("prompt")
    p_veo.add_argument("--model", default="models/veo-3.1-generate-preview")
    p_veo.add_argument("--out-dir", default="/home/user/.openclaw/media/video")
    p_veo.add_argument("--name", default="")
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

    sub.add_parser("rp-discord", help="run Discord RP Mode Runtime")
    p_rph = sub.add_parser("rp-healthcheck", help="check RP runtime integrity and optionally recover runtime-only issues")

    p_rps = sub.add_parser("rp-discord-supervisor", help="run RP discord supervisor (auto-restart)")
    p_rps.add_argument("--min-restart-sec", type=float, default=1.0)
    p_rps.add_argument("--max-restart-sec", type=float, default=20.0)
    p_rps.add_argument("--stable-sec", type=float, default=120.0)

    p_bdr = sub.add_parser("bulk-delete-runtime", help="run Discord bulk-delete queue runtime")
    p_bdr.add_argument("--poll-sec", type=float, default=2.0)
    p_bde = sub.add_parser("bulk-delete-enqueue", help="enqueue Discord bulk-delete job")
    p_bde.add_argument("--channel-id", required=True)
    p_bde.add_argument("--limit", type=int, default=300)
    p_bde.add_argument("--author-id", type=int, default=None)
    p_bde.add_argument("--auto-author", action="store_true", default=True)
    p_bde.add_argument("--no-auto-author", dest="auto_author", action="store_false")
    p_bde.add_argument("--after-message-id", type=int, default=None)
    p_bde.add_argument("--skip-pinned", action="store_true", default=True)
    p_bde.add_argument("--no-skip-pinned", dest="skip_pinned", action="store_false")

    p_gir = sub.add_parser("initial-reset-runtime", help="run git initial-reset queue runtime")
    p_gir.add_argument("--poll-sec", type=float, default=5.0)
    p_gie = sub.add_parser("initial-reset-enqueue", help="enqueue git initial-reset job")
    p_gie.add_argument("--no-latest", action="store_true")
    p_gie.add_argument("--reason", default="")

    p_ghr = sub.add_parser("gitignore-hygiene-runtime", help="run gitignore hygiene queue runtime")
    p_ghr.add_argument("--poll-sec", type=float, default=10.0)
    p_ghe = sub.add_parser("gitignore-hygiene-enqueue", help="enqueue gitignore hygiene job")
    p_ghe.add_argument("--reason", default="")
    p_rph.add_argument("--recover", action="store_true")

    p_fbl = sub.add_parser("feedback-log", help="append auto feedback signal into memory")
    p_fbl.add_argument("text")

    a = p.parse_args()

    if a.cmd == "feedback-log":
        kind = maybe_log_feedback(a.text)
        print(json.dumps({"ok": True, "kind": kind}, ensure_ascii=False))
        return 0

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
            args = [a.prompt, "--model", a.model, "--out-dir", a.out_dir, "--profile", a.profile]
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
            one = _run("generate.py", *args)
            if one != 0:
                rc = one
                break
        append_retro("image", "ok" if rc == 0 else f"fail({rc})", "출력 품질/포맷 편차", "실패 시 프롬프트 1요소만 조정")
        return rc

    if a.cmd == "veo":
        rc = _run("gemini_veo.py", a.prompt, "--model", a.model, "--out-dir", a.out_dir, "--name", a.name, "--poll-seconds", str(a.poll_seconds))
        append_retro("veo", "ok" if rc == 0 else f"fail({rc})", "생성 지연/실패", "실패 시 모델/프롬프트 1개만 조정")
        return rc

    if a.cmd == "rp-discord":
        script = Path('/home/user/.openclaw/workspace/utility/rp/discord_rp_runtime.py')
        try:
            return subprocess.run(["python3", str(script)]).returncode
        except KeyboardInterrupt:
            print("RP Mode Runtime stopped.")
            return 130

    if a.cmd == "rp-discord-supervisor":
        script = Path('/home/user/.openclaw/workspace/utility/rp/rp_supervisor.py')
        return subprocess.run(["python3", str(script),
                               "--min-restart-sec", str(a.min_restart_sec),
                               "--max-restart-sec", str(a.max_restart_sec),
                               "--stable-sec", str(a.stable_sec)]).returncode

    if a.cmd == "rp-healthcheck":
        from utility.rp.rp_engine import runtime_healthcheck

        result = runtime_healthcheck(recover=a.recover)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        rc = 0 if result.get("ok") else 1
        append_retro("rp-healthcheck", "ok" if rc == 0 else "issue", "runtime lock/active room 불일치", "이상 시 RP runtime만 재기동")
        return rc

    if a.cmd == "bulk-delete-runtime":
        script = Path('/home/user/.openclaw/workspace/studio/dashboard/actions/discord_bulk_delete.py')
        rc = subprocess.run(["python3", str(script), "run", "--poll-sec", str(a.poll_sec)]).returncode
        append_retro("bulk-delete-runtime", "ok" if rc == 0 else f"fail({rc})", "동시 실행/잠금 충돌", "큐 상태 확인 후 단일 런타임 유지")
        return rc

    if a.cmd == "bulk-delete-enqueue":
        script = Path('/home/user/.openclaw/workspace/studio/dashboard/actions/discord_bulk_delete.py')
        args = [
            "enqueue",
            "--channel-id", str(a.channel_id),
            "--limit", str(a.limit),
        ]
        if a.author_id is not None:
            args += ["--author-id", str(a.author_id)]
        if a.auto_author:
            args += ["--auto-author"]
        else:
            args += ["--no-auto-author"]
        if a.after_message_id is not None:
            args += ["--after-message-id", str(a.after_message_id)]
        if a.skip_pinned:
            args += ["--skip-pinned"]
        else:
            args += ["--no-skip-pinned"]
        rc = subprocess.run(["python3", str(script), *args]).returncode
        append_retro("bulk-delete-enqueue", "ok" if rc == 0 else f"fail({rc})", "잘못된 채널/옵션 enqueue", "enqueue 결과와 run 로그 교차 확인")
        return rc

    if a.cmd == "initial-reset-runtime":
        script = Path('/home/user/.openclaw/workspace/utility/git/git_initial_reset_runtime.py')
        rc = subprocess.run(["python3", str(script), "run", "--poll-sec", str(a.poll_sec)]).returncode
        append_retro("initial-reset-runtime", "ok" if rc == 0 else f"fail({rc})", "중복 enqueue/강제푸시 리스크", "완료 후 HEAD/원격 해시 확인")
        return rc

    if a.cmd == "initial-reset-enqueue":
        script = Path('/home/user/.openclaw/workspace/utility/git/git_initial_reset_runtime.py')
        args = ["enqueue"]
        if a.no_latest:
            args += ["--no-latest"]
        if a.reason:
            args += ["--reason", a.reason]
        rc = subprocess.run(["python3", str(script), *args]).returncode
        append_retro("initial-reset-enqueue", "ok" if rc == 0 else f"fail({rc})", "중복 초기화 요청", "큐 dedupe 상태 확인")
        return rc

    if a.cmd == "gitignore-hygiene-runtime":
        script = Path('/home/user/.openclaw/workspace/utility/git/gitignore_hygiene_runtime.py')
        rc = subprocess.run(["python3", str(script), "run", "--poll-sec", str(a.poll_sec)]).returncode
        append_retro("gitignore-hygiene-runtime", "ok" if rc == 0 else f"fail({rc})", "추적해제 누락", "tracked-but-ignored 목록 재확인")
        return rc

    if a.cmd == "gitignore-hygiene-enqueue":
        script = Path('/home/user/.openclaw/workspace/utility/git/gitignore_hygiene_runtime.py')
        args = ["enqueue"]
        if a.reason:
            args += ["--reason", a.reason]
        rc = subprocess.run(["python3", str(script), *args]).returncode
        append_retro("gitignore-hygiene-enqueue", "ok" if rc == 0 else f"fail({rc})", "enqueue 파라미터 누락", "run 결과와 git status 동시 확인")
        return rc

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
    rc = _run("pipeline.py", *args)
    append_retro("shorts", "ok" if rc == 0 else f"fail({rc})", "자막/출력 경로 불일치", "실패 시 defaults와 out 경로 우선 확인")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
