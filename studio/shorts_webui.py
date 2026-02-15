#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

WORKSPACE = Path('/home/user/.openclaw/workspace')
PIPELINE = WORKSPACE / 'studio' / 'shorts_pipeline.py'
VENV_PY = WORKSPACE / '.venv' / 'bin' / 'python3'
DEFAULTS_PATH = WORKSPACE / 'studio' / 'shorts_webui_defaults.json'
FONTS_DIR = WORKSPACE / 'fonts'
VOICE_OPTIONS = ['Charon', 'Fenrir', 'Aoede', 'Kore', 'Puck']
DEFAULT_PUBLISH_CHANNEL_ID = '1470802274518433885'
PUBLISH_CHANNEL_OPTIONS = [
    ('1470802274518433885', '요청 채널 (1470802274518433885)'),
]
FONT_OPTIONS = [
    '/home/user/.openclaw/workspace/fonts/SBAggroB.ttf',
    '/home/user/.openclaw/workspace/fonts/BMDOHYEON.otf',
]


def _val(form: dict[str, list[str]], key: str, default: str = '') -> str:
    return (form.get(key, [default])[0] or default).strip()


def _tts_available() -> bool:
    if os.getenv('GEMINI_API_KEY', '').strip():
        return True
    env_path = WORKSPACE / '.env'
    if env_path.exists():
        text = env_path.read_text(encoding='utf-8', errors='ignore')
        return 'GEMINI_API_KEY=' in text
    return False


def _font_options() -> list[str]:
    opts = list(FONT_OPTIONS)
    if FONTS_DIR.exists():
        for p in sorted(FONTS_DIR.glob('*')):
            if p.suffix.lower() in {'.ttf', '.otf'}:
                s = str(p)
                if s not in opts:
                    opts.append(s)
    return opts


def _load_defaults() -> dict[str, str]:
    if not DEFAULTS_PATH.exists():
        return {}
    try:
        data = json.loads(DEFAULTS_PATH.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _safe_name(name: str) -> str:
    raw = ''.join(ch if (ch.isalnum() or ch in '-_') else '_' for ch in name.strip())
    raw = raw.strip('_')
    return raw or 'shorts_test'


def _derive_paths(short_name: str) -> tuple[str, str, str]:
    n = _safe_name(short_name)
    lines = f"/home/user/.openclaw/workspace/media/shorts/lines/{n}_lines.txt"
    subs = f"/home/user/.openclaw/workspace/media/shorts/subs/{n}_subs.txt"
    out = f"/home/user/.openclaw/workspace/media/video/{n}.mp4"
    return lines, subs, out


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def _resolve_youtube_channel_id(raw: str) -> str:
    v = (raw or '').strip()
    if not v:
        return ''
    if v.startswith('UC'):
        return v

    if v.startswith('@'):
        url = f'https://www.youtube.com/{v}'
    elif 'youtube.com/@' in v:
        url = v
    else:
        return v

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html_text = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')
        patterns = [
            r'"channelId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"',
            r'"externalId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"',
            r'"browseId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"',
            r'channel/\s*(UC[0-9A-Za-z_-]{20,})',
        ]
        for pat in patterns:
            m = re.search(pat, html_text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return v


def _split_urls(raw: str) -> list[str]:
    if not raw.strip():
        return []
    tmp = raw.replace('\n', ',').replace(' ', ',')
    out: list[str] = []
    for x in tmp.split(','):
        u = x.strip()
        if u.startswith('http://') or u.startswith('https://'):
            out.append(u)
    return out


def _collect_reliable_image_urls(query: str, limit: int = 6) -> list[str]:
    q = query.strip()
    if not q:
        return []

    urls: list[str] = []

    def add(u: str) -> None:
        if u and u not in urls:
            urls.append(u)

    q_enc = urllib.parse.quote_plus(q)

    # ko/en wikipedia page image
    for lang in ('ko', 'en'):
        try:
            api = (
                f"https://{lang}.wikipedia.org/w/api.php?"
                f"action=query&format=json&generator=search&gsrsearch={q_enc}&gsrlimit=3&"
                "prop=pageimages&piprop=original"
            )
            data = _fetch_json(api)
            pages = (data.get('query') or {}).get('pages') or {}
            for p in pages.values():
                src = ((p.get('original') or {}).get('source') or '').strip()
                add(src)
                if len(urls) >= limit:
                    return urls[:limit]
        except Exception:
            pass

    # wikimedia commons files
    try:
        api = (
            "https://commons.wikimedia.org/w/api.php?"
            f"action=query&format=json&generator=search&gsrsearch={q_enc}%20filetype:bitmap&gsrlimit=5&"
            "prop=imageinfo&iiprop=url"
        )
        data = _fetch_json(api)
        pages = (data.get('query') or {}).get('pages') or {}
        for p in pages.values():
            infos = p.get('imageinfo') or []
            if infos:
                add((infos[0].get('url') or '').strip())
            if len(urls) >= limit:
                return urls[:limit]
    except Exception:
        pass

    return urls[:limit]


def _generate_ai_images(prompt: str, short_name: str, count: int = 3) -> list[str]:
    if not prompt.strip():
        raise ValueError('AI 이미지 모드면 image_prompt를 입력해줘.')

    count = max(3, int(count or 3))

    identity_lock = (
        "한태율 아바타 기반의 동일 캐릭터로 생성. "
        "22세 남성, 한국인, 짧은 검은 머리, 부드러운 인상, 녹색 포인트(#2AA748), "
        "귀엽지만 단정한 분위기. 성별/캐릭터 변경 금지. "
        "기존 아바타 파일을 그대로 복붙하지 말고, 같은 캐릭터의 새로운 일러스트로 생성. "
    )
    out_dir = WORKSPACE / 'media' / 'image'
    out_dir.mkdir(parents=True, exist_ok=True)
    py = str(VENV_PY) if VENV_PY.exists() else 'python3'

    results: list[str] = []
    for idx in range(1, count + 1):
        full_prompt = f"{identity_lock}{prompt.strip()} 시드 변형 {idx}. 구도와 표정을 약간 다르게."
        name = f"{_safe_name(short_name)}_cover_{idx:02d}"
        cmd = [
            py,
            str(WORKSPACE / 'studio' / 'gemini_image.py'),
            full_prompt,
            '--out-dir',
            str(out_dir),
            '--name',
            name,
        ]
        p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, check=False)
        if p.returncode != 0:
            tail = (p.stderr or p.stdout or 'image generation failed')[-400:]
            raise ValueError(f'AI 이미지 생성 실패({idx}/{count}): {tail}')

        found = None
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            cand = out_dir / f"{name}{ext}"
            if cand.exists():
                found = str(cand)
                break
        if not found:
            raise ValueError(f'AI 이미지 생성 결과 파일을 찾지 못했어 ({idx}/{count}).')
        results.append(found)

    return results


def _build_command(form: dict[str, list[str]]) -> list[str]:
    short_name = _val(form, 'short_name', 'shorts_test')
    title = _val(form, 'title')

    d_lines, d_subs, d_out = _derive_paths(short_name)
    lines = _val(form, 'lines', d_lines) or d_lines
    out = _val(form, 'out', d_out) or d_out

    if not title:
        raise ValueError('필수값 누락: title')

    subtitle = _val(form, 'subtitle', '핵심 요약')
    subs = _val(form, 'subs', d_subs)
    use_tts = _val(form, 'use_tts', '') == 'on'
    clean_previous = _val(form, 'clean_previous', 'on') == 'on'
    voice = _val(form, 'voice', 'Charon')
    font = _val(form, 'font', '/home/user/.openclaw/workspace/fonts/SBAggroB.ttf')
    caption_font = _val(form, 'caption_font', '/home/user/.openclaw/workspace/fonts/BMDOHYEON.otf')

    py = str(VENV_PY) if VENV_PY.exists() else 'python3'
    cmd = [
        py, str(PIPELINE),
        '--workspace', str(WORKSPACE / 'studio'),
        '--title', title,
        '--subtitle', subtitle,
        '--font', font,
        '--voice', voice,
        '--out', out,
        '--lines', lines,
        '--title-y', _val(form, 'title_y', '-1'),
        '--subtitle-y', _val(form, 'subtitle_y', '-1'),
        '--caption-y', _val(form, 'caption_y', '-1'),
        '--caption-y-offset', _val(form, 'caption_y_offset', '0'),
        '--top-h', _val(form, 'top_h', '520'),
        '--bottom-h', _val(form, 'bottom_h', '620'),
    ]

    use_web = _val(form, 'use_web', '') == 'on'
    use_ai = _val(form, 'use_ai', '') == 'on'
    prefer_namuwiki = _val(form, 'prefer_namuwiki', '') == 'on'
    prefer_dcinside = _val(form, 'prefer_dcinside', '') == 'on'
    fallback_youtube = _val(form, 'fallback_youtube', 'on') == 'on'

    extra_image_url = _val(form, 'extra_image_url')
    web_query = _val(form, 'web_query', title)
    fallback_channel_id = _resolve_youtube_channel_id(_val(form, 'fallback_channel_id'))
    image_prompt = _val(form, 'image_prompt')
    ai_image_count = _val(form, 'ai_image_count', '3')

    if not (use_web or use_ai):
        raise ValueError('이미지 소스를 최소 1개는 선택해줘. (Web 또는 AI)')

    use_youtube_fallback_now = False

    if use_web:
        manual_urls = _split_urls(extra_image_url)
        tags: list[str] = []
        if prefer_namuwiki:
            tags.append('나무위키')
        if prefer_dcinside:
            tags.append('디시인사이드')
        query = f"{web_query} {' '.join(tags)}".strip()
        auto_urls = _collect_reliable_image_urls(query, limit=6)
        merged: list[str] = []
        for u in (manual_urls + auto_urls):
            if u not in merged:
                merged.append(u)

        if merged:
            for u in merged:
                cmd += ['--extra-image-url', u]
        elif fallback_youtube and fallback_channel_id:
            use_youtube_fallback_now = True
        elif not use_ai:
            raise ValueError('Web 이미지를 찾지 못했고 YouTube fallback도 없어. web_query/URL 또는 AI를 확인해줘.')

    if use_youtube_fallback_now:
        if not fallback_channel_id.startswith('UC'):
            raise ValueError('YouTube fallback 채널을 해석하지 못했어. @handle 대신 UC... 채널ID를 넣어줘.')
        cmd += ['--channel-id', fallback_channel_id]
    else:
        cmd += ['--skip-youtube']

    if use_ai:
        ai_files = _generate_ai_images(image_prompt, short_name, int(ai_image_count or '3'))
        for ai_file in ai_files:
            cmd += ['--extra-image-file', ai_file]
    if not clean_previous:
        cmd += ['--keep-existing']

    if not use_tts:
        cmd += ['--no-tts', '--tts-placeholder-seconds', _val(form, 'tts_placeholder_seconds', '5.0')]
    if subs:
        cmd += ['--subs', subs]
    if caption_font:
        cmd += ['--caption-font', caption_font]

    return cmd


def _publish_to_discord(channel_id: str, out_path: str, title: str) -> tuple[bool, str]:
    cid = (channel_id or '').strip() or DEFAULT_PUBLISH_CHANNEL_ID
    if not cid:
        return False, '업로드 채널 미지정'
    if not cid.isdigit():
        return False, '업로드 채널 ID는 숫자여야 해'

    py = str(VENV_PY) if VENV_PY.exists() else 'python3'
    cmd = [
        py,
        str(WORKSPACE / 'utility' / 'discord' / 'discord_send_media.py'),
        '--channel-id',
        cid,
        '--file',
        out_path,
        '--content',
        f'쇼츠 렌더 완료: {title}',
    ]
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, check=False)
    if p.returncode == 0:
        return True, (p.stdout.strip() or '업로드 완료')
    return False, (p.stderr.strip() or p.stdout.strip() or '업로드 실패')


def _page(body: str) -> bytes:
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>Shorts UI</title>
<style>
:root{{--bg:#0b1020;--card:#131a2d;--line:#2a3658;--text:#e8ecff;--muted:#9fafd9;--accent:#2aa748;--accent2:#4f8cff}}
*{{box-sizing:border-box}}
body{{font-family:Inter,Segoe UI,Arial,sans-serif;max-width:980px;margin:20px auto;padding:0 16px;background:radial-gradient(1200px 500px at 10% -20%,#1c2a52 0%,var(--bg) 55%);color:var(--text)}}
h2{{margin:0 0 6px 0;font-size:26px}}
.desc{{color:var(--muted);margin:0 0 16px 0;font-size:14px}}
.section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 14px 10px;margin:12px 0}}
.section h3{{margin:0 0 8px 0;font-size:15px;color:#d8e2ff}}
label{{display:block;margin-top:10px;font-weight:600;color:#d7e0ff;font-size:13px}}
input{{width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:var(--text)}}
input:focus{{outline:none;border-color:var(--accent2);box-shadow:0 0 0 2px rgba(79,140,255,.2)}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
button{{margin-top:14px;padding:11px 16px;border:0;border-radius:11px;background:linear-gradient(90deg,var(--accent),#2fd37c);color:#fff;font-weight:800;cursor:pointer}}
pre{{white-space:pre-wrap;background:#0c1222;padding:12px;border-radius:10px;border:1px solid #2d3a61;color:#d7e0ff}}
.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#152344;border:1px solid #304777;color:#b4c7ff;font-size:12px;margin-right:6px}}
@media (max-width:780px){{.row{{grid-template-columns:1fr}}}}
</style></head><body>
<h2>Shorts 생성 UI</h2>
<p class="desc">작업 이름 + 제목/부제목 중심으로 빠르게 렌더 실행하는 UI야. 이미지는 Web 자동수집(신뢰 소스 우선)을 기본으로 하고, AI는 필요할 때만 보조로 켤 수 있어.</p>
<div><span class="badge">v1</span><span class="badge">Pipeline 연동</span><span class="badge">로컬 전용</span></div>
{body}
</body></html>'''.encode('utf-8')


def _form(defaults: dict[str, str] | None = None) -> str:
    d = defaults or {}

    def g(k: str, v: str = '') -> str:
        return html.escape(d.get(k, v))

    tts_ok = _tts_available()
    use_tts_checked = (d.get('use_tts') == 'on') if d else tts_ok
    clean_previous = (d.get('clean_previous', 'on') == 'on')

    short_name = d.get('short_name', 'shorts_test')
    d_lines, d_subs, d_out = _derive_paths(short_name)

    use_web = (d.get('use_web', 'on') == 'on')
    use_ai = (d.get('use_ai', '') == 'on')
    prefer_namuwiki = (d.get('prefer_namuwiki', '') == 'on')
    prefer_dcinside = (d.get('prefer_dcinside', '') == 'on')
    fallback_youtube = (d.get('fallback_youtube', 'on') == 'on')

    voice_selected = d.get('voice', 'Charon')
    voice_html = ''.join(
        f'<option value="{html.escape(v)}"' + (' selected' if v == voice_selected else '') + f'>{html.escape(v)}</option>'
        for v in VOICE_OPTIONS
    )

    fonts = _font_options()
    font_selected = d.get('font', '/home/user/.openclaw/workspace/fonts/SBAggroB.ttf')
    caption_font_selected = d.get('caption_font', '/home/user/.openclaw/workspace/fonts/BMDOHYEON.otf')
    font_html = ''.join(
        f'<option value="{html.escape(v)}"' + (' selected' if v == font_selected else '') + f'>{html.escape(v)}</option>'
        for v in fonts
    )
    caption_font_html = ''.join(
        f'<option value="{html.escape(v)}"' + (' selected' if v == caption_font_selected else '') + f'>{html.escape(v)}</option>'
        for v in fonts
    )

    publish_selected = d.get('publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID)
    publish_html = ''.join(
        f'<option value="{html.escape(cid)}"' + (' selected' if cid == publish_selected else '') + f'>{html.escape(label)}</option>'
        for cid, label in PUBLISH_CHANNEL_OPTIONS
    )

    return f'''
<form method="post">
  <div class="section">
    <h3>기본 정보</h3>
    <div class="row">
      <div><label>작업 이름*(파일명 키)</label><input name="short_name" value="{g('short_name','shorts_test')}" placeholder="deltarune_ralsei_v1"></div>
      <div>
        <label>이미지 소스</label>
        <label style="font-weight:500;margin-top:6px;display:flex;align-items:center;gap:8px"><input type="checkbox" name="use_web" {'checked' if use_web else ''} style="width:auto"> Web(기본)</label>
        <label style="font-weight:500;margin-top:4px;display:flex;align-items:center;gap:8px"><input type="checkbox" name="use_ai" {'checked' if use_ai else ''} style="width:auto"> AI(보조/대체)</label>
        <label style="font-weight:500;margin-top:8px;display:flex;align-items:center;gap:8px"><input type="checkbox" name="prefer_namuwiki" {'checked' if prefer_namuwiki else ''} style="width:auto"> 나무위키 우선(웹 검색 가중치)</label>
        <label style="font-weight:500;margin-top:6px;display:flex;align-items:center;gap:8px"><input type="checkbox" name="prefer_dcinside" {'checked' if prefer_dcinside else ''} style="width:auto"> 디시인사이드 우선(웹 검색 가중치)</label>
        <label style="font-weight:500;margin-top:8px;display:flex;align-items:center;gap:8px"><input type="checkbox" name="fallback_youtube" {'checked' if fallback_youtube else ''} style="width:auto"> 웹 실패 시 YouTube fallback</label>
      </div>
    </div>
    <div class="row">
      <div><label>web_query (신빙성 높은 이미지 자동 수집 키워드)</label><input name="web_query" value="{g('web_query')}" placeholder="아이덴티티 김도훈"></div>
      <div><label>fallback_channel_id (YouTube fallback용, 내가 작업마다 채워둘 값)</label><input name="fallback_channel_id" value="{g('fallback_channel_id')}" placeholder="UC... 또는 @handle"></div>
    </div>
    <div class="row">
      <div>
        <label>TTS 사용</label>
        <label style="font-weight:500;margin-top:6px;display:flex;align-items:center;gap:8px">
          <input type="checkbox" name="use_tts" {'checked' if use_tts_checked else ''} style="width:auto"> 사용
        </label>
        <small style="color:#9fafd9">기본값: {'ON' if tts_ok else 'OFF'} (키/환경 감지 기준)</small>
        <label style="font-weight:500;margin-top:8px;display:flex;align-items:center;gap:8px">
          <input type="checkbox" name="clean_previous" {'checked' if clean_previous else ''} style="width:auto"> 실행 전 기존 산출물 삭제(기본)
        </label>
        <label style="margin-top:8px">TTS OFF 시 줄당 길이(초)</label>
        <input name="tts_placeholder_seconds" value="{g('tts_placeholder_seconds','5.0')}">
      </div>
    </div>
    <div class="row">
      <div><label>voice</label><select name="voice" style="width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:#e8ecff">{voice_html}</select></div>
      <div></div>
    </div>
    <label>title*</label><input name="title" value="{g('title')}">
    <label>subtitle</label><input name="subtitle" value="{g('subtitle','핵심 요약')}">
  </div>

  <div class="section">
    <h3>입력/출력 파일</h3>
    <small style="color:#9fafd9">원칙: 작업 이름만 바꾸면 lines/subs/out은 자동 경로로 채워짐. 필요할 때만 직접 수정.</small>
    <div class="row">
      <div><label>lines file*</label><input name="lines" value="{g('lines', d_lines)}"></div>
      <div><label>subs file(optional)</label><input name="subs" value="{g('subs', d_subs)}"></div>
    </div>
    <div class="row">
      <div><label>extra_image_url (선택, 쉼표/줄바꿈으로 여러 URL 가능)</label><input name="extra_image_url" value="{g('extra_image_url')}" placeholder="https://..."></div>
      <div></div>
    </div>
    <label>image_prompt (ai 모드)</label><input name="image_prompt" value="{g('image_prompt')}" placeholder="주제 핵심 인물/장면 + 분위기 + 색감 + 구도 (예: 인물 중심, 시네마틱, 차분한 톤)">
    <label>ai_image_count (ai 모드, 최소 3)</label><input name="ai_image_count" value="{g('ai_image_count','3')}">
    <label>out mp4 path*</label><input name="out" value="{g('out', d_out)}">
    <label>publish_channel_id (성공 시 디스코드 업로드)</label><select name="publish_channel_id" style="width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:#e8ecff">{publish_html}</select>
  </div>

  <div class="section">
    <h3>레이아웃 조정</h3>
    <div class="row">
      <div><label>title_y</label><input name="title_y" value="{g('title_y','-1')}"></div>
      <div><label>subtitle_y</label><input name="subtitle_y" value="{g('subtitle_y','-1')}"></div>
    </div>
    <div class="row">
      <div><label>caption_y</label><input name="caption_y" value="{g('caption_y','-1')}"></div>
      <div><label>caption_y_offset</label><input name="caption_y_offset" value="{g('caption_y_offset','0')}"></div>
    </div>
    <div class="row">
      <div><label>top_h</label><input name="top_h" value="{g('top_h','600')}"></div>
      <div><label>bottom_h</label><input name="bottom_h" value="{g('bottom_h','600')}"></div>
    </div>
  </div>

  <div class="section">
    <h3>폰트</h3>
    <div class="row">
      <div><label>font</label><select name="font" style="width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:#e8ecff">{font_html}</select></div>
      <div><label>caption_font</label><select name="caption_font" style="width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:#e8ecff">{caption_font_html}</select></div>
    </div>
  </div>

  <button type="submit">생성 실행</button>
</form>
'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._send(_page(_form(_load_defaults())))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length).decode('utf-8', errors='replace')
        form = parse_qs(raw)

        defaults = {k: v[0] for k, v in form.items() if v}
        try:
            cmd = _build_command(form)
        except Exception as e:
            body = _form(defaults) + f"<p style='color:#ff7777'>오류: {html.escape(str(e))}</p>"
            self._send(_page(body), 400)
            return

        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            text=True,
            capture_output=True,
            check=False,
        )

        joined = ' '.join(cmd)
        result = f"<h3>실행 명령</h3><pre>{html.escape(joined)}</pre>"
        result += f"<h3>결과 코드</h3><pre>{proc.returncode}</pre>"

        if proc.returncode == 0:
            result += "<p style='color:#7dffa2'>렌더 성공</p>"
            publish_channel_id = _val(form, 'publish_channel_id')
            if publish_channel_id:
                ok, msg = _publish_to_discord(publish_channel_id, _val(form, 'out'), _val(form, 'title'))
                color = '#7dffa2' if ok else '#ff9f7a'
                result += f"<p style='color:{color}'>Discord 업로드: {html.escape(msg)}</p>"
            # 성공 시에는 에러로그를 숨기고 필요한 출력만 보여줌
            if proc.stdout.strip():
                result += f"<h3>stdout</h3><pre>{html.escape(proc.stdout[-3000:])}</pre>"
        else:
            if proc.stdout:
                result += f"<h3>stdout</h3><pre>{html.escape(proc.stdout[-8000:])}</pre>"
            if proc.stderr:
                result += f"<h3>stderr</h3><pre>{html.escape(proc.stderr[-8000:])}</pre>"

        result += _form(defaults)
        self._send(_page(result), 200 if proc.returncode == 0 else 500)


def _run_once_from_defaults() -> int:
    defaults = _load_defaults()
    if not defaults:
        print('defaults 파일이 비어있어: studio/shorts_webui_defaults.json')
        return 2

    form = {k: [str(v)] for k, v in defaults.items()}
    try:
        cmd = _build_command(form)
    except Exception as e:
        print(f'커맨드 생성 실패: {e}')
        return 2

    proc = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if proc.stdout.strip():
            print(proc.stdout[-8000:])
        if proc.stderr.strip():
            print(proc.stderr[-8000:])
        return proc.returncode

    out_path = _val(form, 'out')
    title = _val(form, 'title')
    publish_channel_id = _val(form, 'publish_channel_id')
    if publish_channel_id:
        ok, msg = _publish_to_discord(publish_channel_id, out_path, title)
        print(msg)
        if not ok:
            return 1

    if proc.stdout.strip():
        print(proc.stdout[-2000:])
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description='Shorts local web UI / runner')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8787)
    ap.add_argument('--mode', choices=['ui', 'run'], default='ui', help='ui: 웹UI 실행, run: defaults 기준 즉시 렌더')
    args = ap.parse_args()

    if args.mode == 'run':
        raise SystemExit(_run_once_from_defaults())

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Shorts UI running: http://{args.host}:{args.port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
