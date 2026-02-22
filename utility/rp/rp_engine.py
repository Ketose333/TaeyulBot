#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---- paths/constants ----
ROOMS_DIR = Path('/home/user/.openclaw/workspace/memory/rp_rooms')
ACTIVE_ROOMS_PATH = ROOMS_DIR / '_active_rooms.json'
RUNTIME_LOCK_PATH = ROOMS_DIR / '_runtime_lock.json'
LEGACY_CACHE_PATH = ROOMS_DIR / '_legacy_cache.json'
PREFS_PATH = ROOMS_DIR / '_room_prefs.json'
SESSIONS_INDEX_PATH = Path('/home/user/.openclaw/agents/main/sessions/sessions.json')
MAX_HISTORY = 500
MAX_RECENT_MESSAGE_IDS = 200
PREFS_PROTECTED_KEYS_FIELD = '__protected_keys__'
PREFS_ALLOWLIST_SNAPSHOT_FIELD = '__allowlist_keys__'

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_-]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s or 'room'

@dataclass
class Ctx:
    platform: str
    channel_id: str  # Discord thread id / DM channel id
    user_id: str

def room_id(ctx: Ctx) -> str:
    return f"{_slug(ctx.platform)}_{_slug(ctx.channel_id)}"

def room_json_path(ctx: Ctx) -> Path:
    return ROOMS_DIR / f"{room_id(ctx)}.json"

def room_md_path(ctx: Ctx) -> Path:
    return ROOMS_DIR / f"{room_id(ctx)}.md"

def _append_md(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(line.rstrip() + '\n')

def _load_active_rooms() -> dict[str, Any]:
    if not ACTIVE_ROOMS_PATH.exists():
        return {}
    try:
        obj = json.loads(ACTIVE_ROOMS_PATH.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def _save_active_rooms(data: dict[str, Any]) -> None:
    ACTIVE_ROOMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_ROOMS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# ---- io helpers ----
def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def _parse_csv_ids(raw: str) -> set[str]:
    return {x.strip() for x in (raw or '').replace('\\n', ',').split(',') if x.strip()}

def _allowed_room_pref_keys() -> set[str]:
    """allowlist 채널은 prefs 프루닝에서 항상 보존.

    우선순위:
    1) .env 로더 시도
    2) 환경변수 RP_ALLOWED_CHANNEL_IDS
    3) workspace .env 파일 직접 파싱(폴백)
    """
    try:
        from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
        load_env_prefer_dotenv()
    except Exception:
        pass

    ids = _parse_csv_ids(os.getenv('RP_ALLOWED_CHANNEL_IDS', ''))

    if not ids:
        try:
            env_path = Path('/home/user/.openclaw/workspace/.env')
            raw = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
            for line in raw.splitlines():
                if line.startswith('RP_ALLOWED_CHANNEL_IDS='):
                    ids = _parse_csv_ids(line.split('=', 1)[1].strip())
                    break
        except Exception:
            pass

    return {f"discord_{cid}" for cid in ids}

def _ensure_prefs_protection_metadata(prefs: dict[str, Any]) -> set[str]:
    """allowlist 키를 prefs 내부 metadata로 명시 보존한다."""
    allow_keys = _allowed_room_pref_keys()

    existing = prefs.get(PREFS_PROTECTED_KEYS_FIELD)
    protected = {
        str(k).strip()
        for k in (existing if isinstance(existing, list) else [])
        if str(k).strip().startswith('discord_')
    }
    protected |= allow_keys

    prefs[PREFS_PROTECTED_KEYS_FIELD] = sorted(protected)
    prefs[PREFS_ALLOWLIST_SNAPSHOT_FIELD] = sorted(allow_keys)
    return protected

def _seed_allowlist_pref_keys(prefs: dict[str, Any]) -> bool:
    """allowlist 키 기본 골격을 prefs에 보장한다."""
    changed = False
    for k in _allowed_room_pref_keys():
        if k not in prefs:
            prefs[k] = {}
            changed = True
    return changed

def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False

def acquire_runtime_lock(token_fingerprint: str, pid: int) -> tuple[bool, str]:
    lock = _load_json(RUNTIME_LOCK_PATH)
    if lock:
        old_pid = int(lock.get('pid') or 0)
        old_token = str(lock.get('token_fingerprint') or '')
        if _is_pid_alive(old_pid):
            if old_token and old_token == token_fingerprint:
                return False, f'중복 실행 차단: 같은 토큰으로 이미 실행 중(pid={old_pid})'
            return False, f'중복 실행 차단: 기존 런타임 실행 중(pid={old_pid})'

    payload = {
        'pid': int(pid),
        'token_fingerprint': token_fingerprint,
        'started_at': now_iso(),
        'heartbeat_at': now_iso(),
    }
    _save_json(RUNTIME_LOCK_PATH, payload)
    return True, 'ok'

def touch_runtime_lock(pid: int) -> None:
    lock = _load_json(RUNTIME_LOCK_PATH)
    if not lock:
        return
    if int(lock.get('pid') or 0) != int(pid):
        return
    lock['heartbeat_at'] = now_iso()
    _save_json(RUNTIME_LOCK_PATH, lock)

def release_runtime_lock(pid: int) -> None:
    lock = _load_json(RUNTIME_LOCK_PATH)
    if not lock:
        return
    if int(lock.get('pid') or 0) != int(pid):
        return
    try:
        RUNTIME_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass

def _set_active_room(ctx: Ctx, room: dict[str, Any]) -> None:
    active = _load_active_rooms()
    active[room_id(ctx)] = {
        'platform': ctx.platform,
        'channel_id': ctx.channel_id,
        'parent_channel_id': str(room.get('parent_channel_id') or ''),
        'scope': 'room-only',
        'title': room.get('title', ''),
        'kind': room.get('kind', ''),
        'owner_id': room.get('owner_id', ''),
        'updated_at': now_iso(),
    }
    _save_active_rooms(active)

def _clear_active_room(ctx: Ctx) -> None:
    active = _load_active_rooms()
    key = room_id(ctx)
    if key in active:
        del active[key]
        _save_active_rooms(active)

def load_room(ctx: Ctx) -> dict[str, Any] | None:
    p = room_json_path(ctx)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None

def save_room(ctx: Ctx, room: dict[str, Any]) -> None:
    p = room_json_path(ctx)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(room, ensure_ascii=False, indent=2), encoding='utf-8')

# ---- room lifecycle ----
def start_room(ctx: Ctx, title: str = '', kind: str = 'thread', opening: str = '') -> tuple[bool, str]:
    # 새 룸 생성 전에 활성 룸 제외 레거시 데이터 선청소
    try:
        cleanup_non_active_rooms()
    except Exception:
        pass

    existing = load_room(ctx)
    if existing and existing.get('is_active', True):
        return False, '이미 RP가 시작되어 있어.'

    room = {
        'id': room_id(ctx),
        'title': title.strip(),
        'kind': kind,  # thread | dm
        'parent_channel_id': '',
        'owner_id': ctx.user_id,
        'participants': [ctx.user_id],
        'history': [],
        'opening': opening.strip(),
        'world': {
            'title': '',
            'summary': '',
            'rules': [],
            'tags': [],
        },
        'settings': {
            'tone': 'balanced',
            'rating': 'safe',
            'style': 'narrative',
            'user_alias': get_channel_user_alias(ctx, speaker_id=ctx.user_id),
        },
        'recent_message_ids': [],
        'is_active': True,
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }
    save_room(ctx, room)
    _set_active_room(ctx, room)

    md = room_md_path(ctx)
    _append_md(md, "")
    _append_md(md, "---")
    _append_md(md, room.get('title') or 'RP')
    if opening.strip() and opening.strip() != (room.get('title') or '').strip():
        _append_md(md, opening.strip())

    return True, 'RP 시작했어. 이제 그냥 채팅하면 돼.'

def _cleanup_legacy_cache_for_room(rid: str) -> None:
    cache = _load_json(LEGACY_CACHE_PATH)
    if not cache:
        return
    if rid in cache:
        del cache[rid]
        _save_json(LEGACY_CACHE_PATH, cache)

def end_room(ctx: Ctx) -> tuple[bool, str]:
    room = load_room(ctx)
    if not room:
        return False, '여긴 진행 중인 RP가 없어.'

    room['is_active'] = False
    room['closed_at'] = now_iso()
    room['updated_at'] = room['closed_at']
    room['recent_message_ids'] = []
    room.pop('temp', None)
    save_room(ctx, room)
    _clear_active_room(ctx)
    _cleanup_legacy_cache_for_room(room.get('id') or room_id(ctx))
    _append_md(room_md_path(ctx), "")
    return True, 'RP 종료했어.'

def is_room_active(ctx: Ctx) -> bool:
    room = load_room(ctx)
    return bool(room and room.get('is_active', True))

def is_active_room_channel(channel_id: str) -> bool:
    # RP 활성 룸 채널인지 판별(부모 채널 업무와 분리하기 위한 room-only 스코프)
    cid = str(channel_id or '').strip()
    if not cid:
        return False
    active = _load_active_rooms()
    for _, meta in active.items():
        if str((meta or {}).get('channel_id') or '').strip() == cid:
            return True
    return False

def _derive_scene_anchor(room: dict[str, Any]) -> tuple[str, str]:
    """오프닝/최근 대화 기반 범용 장면 앵커.

    특정 시나리오 키워드에 과적합하지 않고,
    "초기 고정 → 진행 중 완화" 원칙만 유지한다.
    """
    opening = str(room.get('opening') or '').strip()
    history = room.get('history') or []
    recent_turns = history[-8:]
    recent_text = ' '.join(str(t.get('text') or '') for t in recent_turns).strip()
    recent_lower = recent_text.lower()

    turn_count = len(history)

    # 범용 전환 신호(주제/목표/장면 이동)
    transition_kw = [
        '다음', '이제', '그럼', '넘어가', '장면', '전환', '바꾸', '정리',
        'next', 'scene', 'move on', 'switch', 'shift'
    ]
    has_transition = any(k in recent_lower for k in transition_kw)

    if opening:
        # 초반엔 오프닝을 강하게, 이후엔 완화
        if turn_count <= 4:
            return (
                f'현재 장면 앵커: {opening[:160]}',
                '앵커 강도: 높음(초반 맥락 고정, 급격한 이탈 금지)'
            )
        if has_transition:
            return (
                f'현재 장면 앵커: {opening[:120]} (전환 진행 중)',
                '앵커 강도: 중간(현재 대화 흐름 우선, 부드러운 장면 이동 허용)'
            )
        return (
            f'현재 장면 앵커: {opening[:120]}',
            '앵커 강도: 중간(연속성 유지, 무관한 점프 금지)'
        )

    # 오프닝이 없는 룸은 최근 대화 중심
    if recent_text:
        return (
            f'현재 장면 앵커: 최근 대화 흐름 기준({recent_text[:80]})',
            '앵커 강도: 중간(직전 맥락 우선)'
        )

    return ('현재 장면 앵커: 미지정', '앵커 강도: 낮음')

# ---- prompt/reply generation ----
def _build_rp_prompt(room: dict[str, Any], user_display: str, bot_name: str) -> str:
    history = room.get('history') or []
    recent = history[-10:]
    is_early_turn = len(history) <= 2
    world = room.get('world') or {}
    settings = room.get('settings') or {}

    transcript: list[str] = []
    for turn in recent:
        uid = str(turn.get('user_id') or '').strip()
        speaker = str(turn.get('speaker_name') or '').strip()
        if not speaker and uid:
            speaker = f'user-{uid[-4:]}'
        if not speaker:
            speaker = '상대'
        text = str(turn.get('text') or '').strip()
        if text:
            transcript.append(f'- {speaker}: {text}')

    world_summary = str(world.get('summary') or '').strip()
    tone = str(settings.get('tone') or 'balanced').strip()
    # 현재 발화자 기준 alias를 우선 사용(제3자 턴에서 owner alias 오인 방지)
    user_alias = str(user_display or settings.get('user_alias') or '').strip()
    scene_anchor, anchor_strength = _derive_scene_anchor(room)

    early_rule = "0) 첫 반응 단계(초반 1~2턴)여도 반드시 RP 톤으로 답한다. 운영/메타 설명으로 새지 않는다.\n" if is_early_turn else ""
    safety_style = (os.getenv('RP_SAFETY_STYLE', 'default') or 'default').strip().lower()
    immersive_rule = (
        "0-1) RP_SAFETY_STYLE=immersive일 때는 현실 안전 가이드/신고 유도/상담 안내를 직접 출력하지 말고, 캐릭터 행동/감정/대사로만 대응한다.\n"
        if safety_style == 'immersive' else ""
    )

    return (
        f"너는 {bot_name}이며, 디스코드 RP 상대역이다.\n"
        "출력 규칙(하드/소프트):\n"
        + early_rule + immersive_rule +
        "[HARD]\n"
        "1) RP 활성 흐름에서는 메인/운영 개입 없이 캐릭터 반응 중심으로 유지한다.\n"
        "2) 직전 대화 맥락을 이어서 RP로 반응한다.\n"
        "3) 메타 설명/시스템 언급/규칙 재진술 금지.\n"
        "4) 한국어 우선(사용자가 영어를 명시 요청한 경우만 영어 허용).\n"
        "4) 영문 3인칭 소설체(He/She/They 시작) 금지.\n"
        "5) 최근 대화의 발화자 이름을 구분해 제3자 발화 오인을 피한다.\n"
        "6) 문장을 중간에 끊지 말고 자연스럽게 끝맺는다.\n"
        "\n[SOFT]\n"
        "7) 말투/서사 길이는 장면에 맞춰 유동적으로 작성한다(고정 템플릿/고정 2줄 금지).\n"
        "8) 상황 질문/침묵성 발화가 와도 흐름을 멈추지 말고 장면·감정·행동을 제시해 서사를 주도한다.\n"
        "9) 사용자 호칭은 설정 alias를 우선 사용하고, 필요할 때만 자연스럽게 사용한다(과반복 금지).\n"
        "10) 행동/상태 묘사는 기울임체(*...*)를 기본 형식으로 사용하고, 괄호 서술((...), [..], {...})은 사용하지 않는다.\n"
        "11) 직접 대화/행동 중심으로 답한다(관찰자 시점 설명문 단독 출력 회피).\n\n"
        f"RP 톤: {tone}\n"
        f"사용자 호칭: {user_alias}\n"
        f"세계관 요약: {world_summary or '미지정'}\n"
        f"{scene_anchor}\n"
        f"{anchor_strength}\n"
        "최근 대화:\n"
        + ('\n'.join(transcript) if transcript else '- (대화 없음)')
    )

def _looks_truncated(text: str) -> bool:
    t = (text or '').strip()
    if not t:
        return True
    if t.endswith(('…', '...', '…"')):
        return False
    # 문장 종결 부호 없고, 조사/어미에서 끊긴 흔적이면 잘림으로 판단
    if t[-1] in '.!?。！？':
        return False
    bad_tail = ('을', '를', '이', '가', '에', '로', '와', '과', '며', '고', '서', '데', '는', '은')
    if t.endswith(bad_tail):
        return True
    # 마지막 토큰 길이가 너무 짧으면(예: "손을") 잘림 가능성 높음
    last = t.split()[-1] if t.split() else t
    return len(last) <= 2

def _has_placeholder_pattern(text: str) -> bool:
    t = (text or '')
    # 예: [정확한 목적어], [첫 번째 단계]
    return bool(re.search(r'\[[^\]\n]{1,80}\]', t))

def _is_ooc_intervention(reply: str, recent_transcript: str = '') -> bool:
    """키워드 하드코딩 없이, 모델 판정으로 OOC 개입 여부를 감지한다."""
    text = (reply or '').strip()
    if not text:
        return False
    judge_prompt = (
        "다음 RP 답변이 몰입을 깨는 운영자/안전/메타 개입인지 판정해.\n"
        "기준: 캐릭터 대사/행동이 아니라 현실 조언/훈계/운영 안내가 중심이면 UNSAFE.\n"
        "캐릭터 반응 중심이면 SAFE.\n"
        "출력은 SAFE 또는 UNSAFE 한 단어만.\n\n"
        f"최근대화:\n{(recent_transcript or '')[:1200]}\n\n"
        f"후보답변:\n{text}"
    )
    try:
        out = _call_gemini_text(judge_prompt).strip().upper()
        return out.startswith('UNSAFE')
    except Exception:
        return False

def _call_gemini_text(prompt: str) -> str:
    api_key = (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('missing GEMINI_API_KEY/GOOGLE_API_KEY')

    model = (os.getenv('RP_LLM_MODEL') or 'gemini-2.5-flash').strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    generation_config: dict[str, Any] = {
        'temperature': float(os.getenv('RP_LLM_TEMPERATURE', '0.9')),
    }
    # 0 이하면 maxOutputTokens를 강제하지 않음(모델 기본 상한 사용)
    max_tokens = int(os.getenv('RP_LLM_MAX_TOKENS', '0'))
    if max_tokens > 0:
        generation_config['maxOutputTokens'] = max_tokens

    body = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': generation_config,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode('utf-8', errors='replace'))

    cands = payload.get('candidates') or []
    if not cands:
        raise RuntimeError('empty candidates')
    parts = (((cands[0] or {}).get('content') or {}).get('parts') or [])
    text = ''.join(str(p.get('text') or '') for p in parts).strip()
    if not text:
        raise RuntimeError('empty text')
    return text

def generate_rp_opening(user_alias: str, opening: str = '', bot_name: str = 'RP') -> str:
    alias = (user_alias or '너').strip()
    seed = (opening or '').strip()
    prompt = (
        f"너는 {bot_name}이며 디스코드 RP 상대역이다.\n"
        "오프닝만 작성한다. 템플릿 문구 금지.\n"
        "출력 규칙:\n"
        "1) 정확히 2줄\n"
        "2) 1줄은 기울임체 행동(별표로 감싸기)\n"
        "3) 2줄은 대사(따옴표/볼드 금지)\n"
        "4) 메타 문장 금지(예: 장면의 첫 문장, 시작하자 같은 운영 문구 금지)\n"
        "5) 사용자 이름/호칭은 과하게 반복하지 말고 자연스럽게 필요할 때만 0~1회 사용\n"
        f"사용자 호칭: {alias}\n"
        f"주제: {seed or '새로운 장면'}"
    )
    try:
        out = _call_gemini_text(prompt)
        text = (out or '').replace('**', '').replace('"', '').strip()
        if _has_placeholder_pattern(text):
            out = _call_gemini_text(prompt + "\n\n금지: 대괄호 플레이스홀더([예시])를 절대 출력하지 마.")
            text = (out or '').replace('**', '').replace('"', '').strip()
        if _has_placeholder_pattern(text):
            return ''
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return f"{lines[0]}\n{lines[1]}"
    except Exception:
        pass

    # fallback 제거: 실패 시 무출력
    return ''

def generate_rp_reply(ctx: Ctx, user_display: str = '상대', bot_name: str = 'RP') -> str:
    room = load_room(ctx) or {}
    prompt = _build_rp_prompt(room, user_display=user_display, bot_name=bot_name)
    try:
        out = _call_gemini_text(prompt)
        cleaned = (out or '').replace('**', '').replace('"', '').strip()
        if _has_placeholder_pattern(cleaned):
            out = _call_gemini_text(prompt + "\n\n금지: 대괄호 플레이스홀더([예시])를 절대 출력하지 마.")
            cleaned = (out or '').replace('**', '').replace('"', '').strip()
        if _has_placeholder_pattern(cleaned):
            return ''
        if _looks_truncated(cleaned):
            retry_prompt = prompt + "\n\n방금 출력이 중간에 잘렸어. 같은 장면을 완결 문장으로 다시 출력해."
            out2 = _call_gemini_text(retry_prompt)
            cleaned2 = (out2 or '').replace('**', '').replace('"', '').strip()
            if cleaned2 and (not _has_placeholder_pattern(cleaned2)):
                cleaned = cleaned2
        return cleaned
    except Exception:
        return ''

# ---- runtime hygiene/report ----
def runtime_healthcheck(recover: bool = False) -> dict[str, Any]:
    active = _load_active_rooms()
    issues: list[str] = []
    removed: list[str] = []

    for rid, meta in list(active.items()):
        plat = str(meta.get('platform') or 'discord')
        cid = str(meta.get('channel_id') or '')
        if not cid:
            issues.append(f'{rid}: missing channel_id')
            if recover:
                del active[rid]
                removed.append(rid)
            continue

        ctx = Ctx(platform=plat, channel_id=cid, user_id=str(meta.get('owner_id') or '0'))
        room = load_room(ctx)
        if not room or not room.get('is_active', False):
            issues.append(f'{rid}: dangling active index')
            if recover:
                del active[rid]
                removed.append(rid)

    if recover and removed:
        _save_active_rooms(active)

    lock = _load_json(RUNTIME_LOCK_PATH)
    lock_ok = True
    if lock:
        pid = int(lock.get('pid') or 0)
        if not _is_pid_alive(pid):
            lock_ok = False
            issues.append('runtime lock is stale')
            if recover:
                try:
                    RUNTIME_LOCK_PATH.unlink(missing_ok=True)
                except Exception:
                    pass

    return {
        'ok': not issues,
        'issues': issues,
        'recovered': removed,
        'lock_ok': lock_ok,
    }

def ingest_plain_chat(ctx: Ctx, text: str, message_id: str = '', speaker_name: str = '') -> bool:
    content = (text or '').strip()
    if not content:
        return False

    room = load_room(ctx)
    if not room or not room.get('is_active', True):
        return False

    message_id = (message_id or '').strip()
    if message_id:
        seen = room.setdefault('recent_message_ids', [])
        if message_id in seen:
            return False
        seen.append(message_id)
        room['recent_message_ids'] = seen[-MAX_RECENT_MESSAGE_IDS:]

    if ctx.user_id not in room.get('participants', []):
        room.setdefault('participants', []).append(ctx.user_id)

    turn = {
        'user_id': ctx.user_id,
        'speaker_name': (speaker_name or '').strip(),
        'text': content,
        'at': now_iso(),
        'message_id': message_id,
    }
    room.setdefault('history', []).append(turn)
    room['history'] = room['history'][-MAX_HISTORY:]
    room['updated_at'] = now_iso()
    save_room(ctx, room)
    _set_active_room(ctx, room)

    speaker = (turn.get('speaker_name') or '').strip()
    if not speaker:
        speaker = get_channel_user_alias(ctx, speaker_id=ctx.user_id) or '상대'
    _append_md(room_md_path(ctx), f"{speaker}: {turn['text']}")
    return True

def _channel_key(ctx: Ctx) -> str:
    return f"{_slug(ctx.platform)}_{_slug(ctx.channel_id)}"

def set_channel_user_alias(ctx: Ctx, alias: str, speaker_id: str = '') -> None:
    """호칭 설정.
    - speaker_id 없으면 채널 기본(default)
    - speaker_id 있으면 해당 발화자 전용(alias_by_user)
    """
    prefs = _load_json(PREFS_PATH)
    key = _channel_key(ctx)
    item = prefs.get(key) if isinstance(prefs.get(key), dict) else {}
    alias = (alias or '').strip()
    sid = (speaker_id or '').strip()

    if sid:
        per = item.get('alias_by_user') if isinstance(item.get('alias_by_user'), dict) else {}
        if alias:
            per[sid] = alias
            item['alias_by_user'] = per
            prefs[key] = item
        else:
            if sid in per:
                del per[sid]
            if per:
                item['alias_by_user'] = per
                prefs[key] = item
            else:
                item.pop('alias_by_user', None)
                if item:
                    prefs[key] = item
                elif key in prefs:
                    del prefs[key]
    else:
        if alias:
            item['user_alias'] = alias
            prefs[key] = item
        else:
            if key in prefs and isinstance(prefs[key], dict) and 'user_alias' in prefs[key]:
                del prefs[key]['user_alias']
                if not prefs[key]:
                    del prefs[key]

    # 비정상적으로 {}로 떨어지는 것을 막기 위해 allowlist 키 골격을 항상 유지
    _seed_allowlist_pref_keys(prefs)
    _save_json(PREFS_PATH, prefs)

def get_channel_user_alias(ctx: Ctx, speaker_id: str = '') -> str:
    prefs = _load_json(PREFS_PATH)
    item = prefs.get(_channel_key(ctx)) if isinstance(prefs, dict) else None
    if not isinstance(item, dict):
        return ''

    sid = (speaker_id or '').strip()
    if sid:
        per = item.get('alias_by_user') if isinstance(item.get('alias_by_user'), dict) else {}
        alias = str(per.get(sid) or '').strip()
        if alias:
            return alias
    return str(item.get('user_alias') or '').strip()

def _find_legacy_rp_channel_sessions(stale_channel_ids: set[str]) -> list[str]:
    """sessions 인덱스에서 과거 RP 스레드 채널 세션 흔적 후보를 수집한다(비파괴, 리포트 전용)."""
    if not stale_channel_ids:
        return []
    try:
        if not SESSIONS_INDEX_PATH.exists():
            return []
        obj = json.loads(SESSIONS_INDEX_PATH.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            return []
    except Exception:
        return []

    out: list[str] = []
    prefix = 'agent:main:discord:channel:'
    for k in obj.keys():
        if not isinstance(k, str) or not k.startswith(prefix):
            continue
        channel_id = k.rsplit(':', 1)[-1].strip()
        if channel_id in stale_channel_ids:
            out.append(k)
    return sorted(out)

def cleanup_non_active_rooms() -> dict[str, Any]:
    """비활성 룸 청소(비파괴).

    정식 운영 단계에서는 과거 룸 대화 내역(json/md)을 삭제하지 않고,
    인덱스/캐시만 정리한다.
    """
    active = _load_active_rooms()
    active_ids = set(active.keys())

    # 레거시 캐시는 활성 룸 키만 유지
    cache_pruned = 0
    cache = _load_json(LEGACY_CACHE_PATH)
    if cache:
        before = len(cache)
        new_cache = {k: v for k, v in cache.items() if k in active_ids}
        cache_pruned = max(0, before - len(new_cache))
        if new_cache != cache:
            _save_json(LEGACY_CACHE_PATH, new_cache)

    # room prefs는 청소/프루닝에서 건드리지 않음(삭제 관련 제거)
    # 단, 비정상적으로 비어있으면 allowlist 키 골격을 자동 복구
    prefs_pruned = 0
    prefs = _load_json(PREFS_PATH)
    if prefs is not None:
        if _seed_allowlist_pref_keys(prefs):
            _save_json(PREFS_PATH, prefs)

    # 기록 파일은 삭제하지 않음
    json_files = list(ROOMS_DIR.glob('discord_*.json'))
    preserved_json = len(json_files)
    preserved_md = len(list(ROOMS_DIR.glob('discord_*.md')))

    # 레거시 점검 시 과거 RP 스레드 채널 세션 흔적도 함께 리포트
    room_channel_ids = {p.stem.split('discord_', 1)[1] for p in json_files if p.stem.startswith('discord_')}
    active_channel_ids = {rid.split('discord_', 1)[1] for rid in active_ids if rid.startswith('discord_')}
    stale_channel_ids = room_channel_ids - active_channel_ids
    legacy_session_candidates = _find_legacy_rp_channel_sessions(stale_channel_ids)

    return {
        'activeCount': len(active_ids),
        'preservedJsonCount': preserved_json,
        'preservedMdCount': preserved_md,
        'cachePruned': cache_pruned,
        'prefsPruned': prefs_pruned,
        'legacyChannelSessionCount': len(legacy_session_candidates),
        'legacyChannelSessions': legacy_session_candidates,
        'removedCount': 0,
        'removedFiles': [],
    }

def handle_command(ctx: Ctx, text: str) -> tuple[bool, str]:
    raw = text.strip()
    if not raw.startswith('!rp'):
        return False, ''

    parts = raw.split()
    if len(parts) < 2:
        return True, '명령: !rp 시작 / !rp 끝'

    cmd = parts[1]
    if cmd == '시작':
        opening = raw.split(None, 2)[2].strip() if len(parts) >= 3 else ''
        return start_room(ctx, opening=opening)

    if cmd == '끝':
        return end_room(ctx)

    return True, '명령은 !rp 시작 / !rp 끝 두 가지만 써줘.'

# ---- cli entry ----
def main() -> int:
    ap = argparse.ArgumentParser(description='RP engine utilities')
    ap.add_argument('--cleanup-non-active', action='store_true', help='non-destructive cleanup for non-active room indexes/caches')
    ap.add_argument('--platform', default='discord')
    ap.add_argument('--channel-id')
    ap.add_argument('--user-id')
    ap.add_argument('--text')
    ap.add_argument('--message-id', default='')
    args = ap.parse_args()

    if args.cleanup_non_active:
        result = cleanup_non_active_rooms()
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if not (args.channel_id and args.user_id and args.text):
        ap.error('--channel-id, --user-id, --text are required unless --cleanup-non-active is used')

    ctx = Ctx(args.platform, args.channel_id, args.user_id)
    is_cmd, msg = handle_command(ctx, args.text)
    if is_cmd:
        print(msg)
    else:
        ok = ingest_plain_chat(ctx, args.text, message_id=args.message_id, speaker_name='cli-user')
        print('INGESTED' if ok else 'IGNORED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
