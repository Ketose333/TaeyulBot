#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

WORKSPACE = Path('/home/user/.openclaw/workspace')
PRESETS_DIR = WORKSPACE / 'studio' / 'image' / 'presets'
NORMALIZER = PRESETS_DIR / 'normalize_preset_json.py'
VENV_PY = WORKSPACE / '.venv' / 'bin' / 'python3'
SCHEMA_KEYS = [
    'name', 'description', 'model', 'profile', 'aspect_ratio',
    'count', 'prompt', 'output_name_pattern', 'purge_existing_outputs', 'ref_image'
]
PROFILE_OPTIONS = ['taeyul', 'ketose', 'kwonjinhyuk', 'default']
DEFAULT_PUBLISH_CHANNEL_ID = '1470802274518433885'


def _val(form: dict[str, list[str]], key: str, default: str = '') -> str:
    return (form.get(key, [default])[0] or default).strip()


def _preset_files() -> list[Path]:
    return sorted(p for p in PRESETS_DIR.glob('*_preset.json') if p.is_file())


def _load_preset(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _ordered_preset(raw: dict) -> dict:
    out: dict = {}
    defaults = {
        'model': 'nano-banana-pro-preview',
        'profile': 'ketose',
        'aspect_ratio': '1:1',
        'count': 1,
        'purge_existing_outputs': True,
    }
    for k in SCHEMA_KEYS:
        if k in raw:
            out[k] = raw[k]
        elif k in defaults:
            out[k] = defaults[k]
    for k, v in raw.items():
        if k not in out:
            out[k] = v
    return out


def _save_preset(path: Path, data: dict) -> None:
    ordered = _ordered_preset(data)
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _run_normalizer() -> tuple[bool, str]:
    py = str(VENV_PY) if VENV_PY.exists() else 'python3'
    p = subprocess.run([py, str(NORMALIZER)], cwd=str(WORKSPACE), text=True, capture_output=True)
    msg = (p.stdout or p.stderr or '').strip()
    return p.returncode == 0, msg


def _run_preset(preset_name: str) -> tuple[bool, str, list[str]]:
    preset_path = PRESETS_DIR / f'{preset_name}_preset.json'
    if not preset_path.exists():
        return False, f'Preset not found: {preset_name}', []

    try:
        preset = _load_preset(preset_path)
        count = max(1, int(preset.get('count', 1)))
        prompt = str(preset.get('prompt', '')).strip()
        if not prompt:
            return False, 'preset prompt가 비어있어.', []

        profile = str(preset.get('profile', 'ketose'))
        aspect_ratio = str(preset.get('aspect_ratio', '1:1'))
        model = str(preset.get('model', 'nano-banana-pro-preview'))
        name_pattern = str(preset.get('output_name_pattern', f'{preset_name}_{{n}}.jpg'))
        purge_existing_outputs = bool(preset.get('purge_existing_outputs', True))

        ref_image = str(preset.get('ref_image', '')).strip()
        if ref_image:
            rp = Path(ref_image).expanduser().resolve()
            if not rp.exists() or not rp.is_file():
                return False, f'ref_image not found: {rp}', []
            image_root = Path('/home/user/.openclaw/media/image').resolve()
            try:
                rp.relative_to(image_root)
                return False, '재귀참조 방지: /home/user/.openclaw/media/image 아래 파일은 ref_image로 금지', []
            except ValueError:
                pass

        py = str(VENV_PY) if VENV_PY.exists() else 'python3'
        logs: list[str] = [f"[preset] {preset_path.name} count={count} purge={purge_existing_outputs}"]
        media: list[str] = []
        purge_glob = name_pattern.replace('{n}', '*') if purge_existing_outputs else ''

        for i in range(1, count + 1):
            name = name_pattern.replace('{n}', str(i))
            cmd = [
                py, str(WORKSPACE / 'studio' / 'image' / 'generate.py'), prompt,
                '--model', model,
                '--profile', profile,
                '--aspect-ratio', aspect_ratio,
                '--emit-media',
                '--name', name,
            ]
            if ref_image:
                cmd += ['--ref-image', str(Path(ref_image).expanduser().resolve())]
            if purge_glob and i == 1:
                cmd += ['--purge-glob', purge_glob]

            p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
            merged = ((p.stdout or '') + '\n' + (p.stderr or '')).strip()
            if merged:
                logs.append(merged)
            for line in merged.splitlines():
                line = line.strip()
                if line.startswith('MEDIA:'):
                    media.append(line[6:].strip())
            if p.returncode != 0:
                return False, '\n'.join(logs)[-8000:], media

        return True, '\n'.join(logs)[-8000:], media
    except Exception as e:
        return False, str(e), []



def _run_direct(form: dict[str, list[str]]) -> tuple[bool, str, list[str]]:
    prompt = _val(form, 'direct_prompt').strip()
    if not prompt:
        return False, '즉시 실행 프롬프트를 입력해줘.', []

    model = _val(form, 'direct_model', 'nano-banana-pro-preview')
    profile = _val(form, 'direct_profile', 'ketose')
    aspect_ratio = _val(form, 'direct_aspect_ratio', '1:1')
    count = max(1, int(_val(form, 'direct_count', '1') or '1'))
    name_pattern = _val(form, 'direct_name_pattern', 'direct_image_{n}.jpg')
    purge = _val(form, 'direct_purge') == 'on'

    py = str(VENV_PY) if VENV_PY.exists() else 'python3'
    logs: list[str] = [f"[direct] count={count} purge={purge}"]
    media: list[str] = []
    purge_glob = name_pattern.replace('{n}', '*') if purge else ''

    for i in range(1, count + 1):
        name = name_pattern.replace('{n}', str(i))
        cmd = [
            py, str(WORKSPACE / 'studio' / 'image' / 'generate.py'), prompt,
            '--model', model,
            '--profile', profile,
            '--aspect-ratio', aspect_ratio,
            '--emit-media',
            '--name', name,
        ]
        if purge_glob and i == 1:
            cmd += ['--purge-glob', purge_glob]

        proc = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
        merged = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
        if merged:
            logs.append(merged)
        for line in merged.splitlines():
            line = line.strip()
            if line.startswith('MEDIA:'):
                media.append(line[6:].strip())
        if proc.returncode != 0:
            return False, '\n'.join(logs)[-8000:], media

    return True, '\n'.join(logs)[-8000:], media

def _upload_discord(channel_id: str, media_path: str, content: str = '') -> tuple[bool, str]:
    py = str(VENV_PY) if VENV_PY.exists() else 'python3'
    cmd = [
        py,
        str(WORKSPACE / 'utility' / 'discord' / 'discord_send_media.py'),
        '--channel-id', str(channel_id),
        '--file', media_path,
    ]
    if content.strip():
        cmd += ['--content', content.strip()]
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
    msg = (p.stdout or p.stderr or '').strip()
    return p.returncode == 0, (msg or ('업로드 완료' if p.returncode == 0 else '업로드 실패'))


def _build_upload_caption(prompt: str, requested_model: str, logs: str) -> str:
    req = (requested_model or '').strip()
    prompt_line = f"프롬프트: {(prompt or '').strip()}"
    req_line = f"요청 모델: {req}"

    fallback_model = ''
    for line in reversed((logs or '').splitlines()):
        t = line.strip()
        if t.startswith('fallback model:'):
            fallback_model = t.split(':', 1)[1].strip()
            break

    if fallback_model:
        used = fallback_model.replace('models/', '').strip()
        used_line = f"실사용 모델: {used} (fallback from {req})"
        return "\n".join([prompt_line, req_line, used_line])

    return "\n".join([prompt_line, req_line])


def _try_auto_port_proxy(port: int) -> tuple[bool, str]:
    # Best effort only (requires elevated PowerShell)
    ps = WORKSPACE / 'utility' / 'common' / 'windows_wsl_portproxy_autoupdate.ps1'
    if not ps.exists():
        return False, 'portproxy 스크립트 없음'
    cmd = [
        'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(ps), '-Ports', str(port)
    ]
    try:
        p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, timeout=20)
        if p.returncode == 0:
            return True, 'Windows 포트 연결 자동 설정 완료'
        return False, (p.stderr or p.stdout or 'Windows 포트 연결 실패').strip()[-300:]
    except Exception as e:
        return False, f'Windows 포트 연결 스킵: {e}'


def _load_publish_allowlist() -> list[tuple[str, str]]:
    file_path = WORKSPACE / 'studio' / 'publish_channels_allowlist.json'
    out: list[tuple[str, str]] = []

    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                for row in data:
                    if not isinstance(row, dict):
                        continue
                    cid = str(row.get('id', '')).strip()
                    label = str(row.get('label', '')).strip() or f'채널 {cid}'
                    if cid.isdigit():
                        out.append((cid, f'{label} ({cid})'))
            elif isinstance(data, dict):
                for cid, label in data.items():
                    cid = str(cid).strip()
                    if cid.isdigit():
                        name = str(label).strip() or f'채널 {cid}'
                        out.append((cid, f'{name} ({cid})'))
        except Exception:
            out = []

    dedup: dict[str, str] = {}
    for cid, label in out:
        dedup[cid] = label
    return sorted(dedup.items(), key=lambda x: x[1].lower())


def _discord_publish_channel_options() -> list[tuple[str, str]]:
    default_opt = (DEFAULT_PUBLISH_CHANNEL_ID, f'요청 채널 ({DEFAULT_PUBLISH_CHANNEL_ID})')
    allowed = _load_publish_allowlist()
    if not allowed:
        return [default_opt]
    if not any(cid == DEFAULT_PUBLISH_CHANNEL_ID for cid, _ in allowed):
        return [default_opt] + allowed
    return allowed


def _local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def _form(selected: str, data: dict, alert: str = '') -> bytes:
    presets = _preset_files()
    options = ''.join(
        f"<option value='{html.escape(p.stem.replace('_preset',''))}'" + (" selected" if p.stem.replace('_preset','') == selected else '') + f">{html.escape(p.name)}</option>"
        for p in presets
    )

    def g(k: str, d: str = '') -> str:
        v = data.get(k, d)
        if isinstance(v, bool):
            return 'on' if v else ''
        return html.escape(str(v))

    alert_html = f"<div class='alert'>{html.escape(alert)}</div>" if alert else ''
    checked = 'checked' if data.get('purge_existing_outputs', True) else ''
    selected_profile = str(data.get('profile', 'ketose'))
    profile_options_html = ''.join(
        f"<option value='{html.escape(v)}'" + (" selected" if v == selected_profile else '') + f">{html.escape(v)}</option>"
        for v in PROFILE_OPTIONS
    )
    selected_upload_channel = str(data.get('_publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID))
    upload_options_html = ''.join(
        f"<option value='{html.escape(cid)}'" + (" selected" if cid == selected_upload_channel else '') + f">{html.escape(label)}</option>"
        for cid, label in _discord_publish_channel_options()
    )
    upload_caption_checked = 'checked' if bool(data.get('_upload_with_caption', True)) else ''

    body = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>Image Preset UI</title>
<style>
:root{{--bg:#0b1020;--card:#131a2d;--line:#2a3658;--text:#e8ecff;--muted:#9fafd9;--accent:#2aa748;--accent2:#4f8cff}}
*{{box-sizing:border-box}}
body{{font-family:Inter,Segoe UI,Arial,sans-serif;max-width:980px;margin:20px auto;padding:0 16px;background:radial-gradient(1200px 500px at 10% -20%,#1c2a52 0%,var(--bg) 55%);color:var(--text)}}
h2{{margin:0 0 6px 0;font-size:26px}}
.desc{{color:var(--muted);margin:0 0 16px 0;font-size:14px}}
.section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 14px 10px;margin:12px 0}}
.section h3{{margin:0 0 8px 0;font-size:15px;color:#d8e2ff}}
label{{display:block;margin-top:10px;font-weight:600;color:#d7e0ff;font-size:13px}}
input,textarea,select{{width:100%;padding:9px 10px;border-radius:10px;border:1px solid #3a4a79;background:#0f1527;color:var(--text)}}
input:focus,textarea:focus,select:focus{{outline:none;border-color:var(--accent2);box-shadow:0 0 0 2px rgba(79,140,255,.2)}}
textarea{{min-height:120px;resize:vertical}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.action-row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}
button{{padding:11px 16px;border:0;border-radius:11px;background:linear-gradient(90deg,var(--accent),#2fd37c);color:#fff;font-weight:800;cursor:pointer}}
button.secondary{{background:#1f2b47;border:1px solid #3a4a79}}
.alert{{background:#133222;border:1px solid #2aa748;padding:10px;border-radius:10px;white-space:pre-wrap}}
.checkline{{display:flex;align-items:center;gap:8px;font-weight:500;color:#d7e0ff;margin-top:12px}}
.checkline input{{width:auto;margin:0}}
.badges{{margin-bottom:10px}}
.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#152344;border:1px solid #304777;color:#b4c7ff;font-size:12px;margin-right:6px}}
@media (max-width:780px){{.row{{grid-template-columns:1fr}}}}
</style></head><body>
<h2>이미지 생성 UI</h2>
<p class='desc'>쇼츠 UI와 같은 리듬으로 정리한 이미지 생성 화면이야. 프리셋 저장/실행과 즉시 실행을 한 화면에서 처리해.</p>
<div class='badges'><span class='badge'>Preset</span><span class='badge'>Direct Run</span><span class='badge'>Upload</span></div>
{alert_html}
<form method='post'>
  <div class='section'>
    <h3>프리셋 선택 · 작업</h3>
    <label>프리셋</label>
    <select name='preset'>{options}</select>
    <div class='action-row'>
      <button name='action' value='save' type='submit'>저장</button>
      <button name='action' value='load' type='submit' class='secondary'>불러오기</button>
      <button name='action' value='normalize' type='submit' class='secondary'>형식 정규화</button>
      <button name='action' value='run' type='submit'>생성 실행</button>
    </div>
  </div>

  <div class='section'>
    <h3>기본 정보 · 프리셋 설정</h3>
    <div class='row'>
      <div><label>이름(name)</label><input name='name' value='{g('name')}'></div>
      <div><label>설명(description)</label><input name='description' value='{g('description')}'></div>
    </div>
    <div class='row'>
      <div><label>모델(model)</label><input name='model' value='{g('model','nano-banana-pro-preview')}'><small style='color:#9fafd9;display:block;margin-top:6px'>기본값: nano-banana-pro-preview</small></div>
      <div><label>프로필(profile)</label><select name='profile'>{profile_options_html}</select></div>
    </div>
    <div class='row'>
      <div><label>비율(aspect_ratio)</label><input name='aspect_ratio' value='{g('aspect_ratio','1:1')}'><small style='color:#9fafd9;display:block;margin-top:6px'>기본값: 1:1</small></div>
      <div><label>생성 개수(count)</label><input name='count' value='{g('count','1')}'><small style='color:#9fafd9;display:block;margin-top:6px'>기본값: 1</small></div>
    </div>
    <label>출력 파일 패턴(output_name_pattern)</label><input name='output_name_pattern' value='{g('output_name_pattern')}'>
    <label>레퍼런스 이미지(ref_image, 선택)</label><input name='ref_image' value='{g('ref_image')}'>
    <label class='checkline'><input type='checkbox' name='purge_existing_outputs' {checked}> 기존 출력 정리 후 생성(purge_existing_outputs)</label>
    <label>요청 프롬프트(prompt)</label><textarea name='prompt'>{g('prompt')}</textarea>
  </div>

  <div class='section'>
    <h3>입력 설정 · 즉시 실행 (저장 없이 1회 생성)</h3>
    <label>자연어 요청 프롬프트</label><textarea name='direct_prompt'>{g('_direct_prompt')}</textarea>
    <div class='row'>
      <div><label>모델(model)</label><input name='direct_model' value='{g('_direct_model','nano-banana-pro-preview')}'></div>
      <div><label>프로필(profile)</label><select name='direct_profile'>{''.join(f"<option value='{html.escape(v)}'" + (" selected" if v == str(data.get('_direct_profile','ketose')) else '') + f">{html.escape(v)}</option>" for v in PROFILE_OPTIONS)}</select></div>
    </div>
    <div class='row'>
      <div><label>비율(aspect_ratio)</label><input name='direct_aspect_ratio' value='{g('_direct_aspect_ratio','1:1')}'></div>
      <div><label>생성 개수(count)</label><input name='direct_count' value='{g('_direct_count','1')}'></div>
    </div>
    <label>출력 파일 패턴(output_name_pattern)</label><input name='direct_name_pattern' value='{g('_direct_name_pattern','direct_image_{n}.jpg')}'>
    <label class='checkline'><input type='checkbox' name='direct_purge' {'checked' if data.get('_direct_purge', True) else ''}> 기존 출력 정리 후 생성(direct_purge)</label>
    <small style='color:#9fafd9;display:block;margin-top:6px'>디스코드에서 요청하던 자연어 문장을 그대로 넣으면 돼.</small>
    <div class='action-row'><button name='action' value='run_direct' type='submit'>즉시 실행</button></div>
  </div>

  <div class='section'>
    <h3>배포</h3>
    <label>publish_channel_id (allowlist + DM 고정 dropdown)</label><select name='publish_channel_id'>{upload_options_html}</select>
    <label class='checkline'><input type='checkbox' name='upload_with_caption' {upload_caption_checked}> 업로드 시 프롬프트/모델 문구 함께 첨부</label>
  </div>

</form>
</body></html>
"""
    return body.encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        files = _preset_files()
        if not files:
            self._send(_form('', {}, '프리셋 파일이 없어. studio/image/presets/*_preset.json 확인해줘'), 200)
            return
        p = files[0]
        d = _load_preset(p)
        d['_publish_channel_id'] = DEFAULT_PUBLISH_CHANNEL_ID
        d['_upload_with_caption'] = True
        self._send(_form(p.stem.replace('_preset', ''), d))

    def do_POST(self):  # noqa: N802
        ln = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(ln).decode('utf-8', errors='replace')
        form = parse_qs(raw)

        preset_name = _val(form, 'preset')
        preset_path = PRESETS_DIR / f'{preset_name}_preset.json'
        action = _val(form, 'action', 'load')

        if action != 'run_direct' and (not preset_path.exists()):
            self._send(_form(preset_name, {}, f'프리셋 없음: {preset_path.name}'), 404)
            return

        alert = ''
        data = _load_preset(preset_path)
        data['_publish_channel_id'] = _val(form, 'publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID)
        data['_upload_with_caption'] = (_val(form, 'upload_with_caption') == 'on')

        if action == 'save':
            try:
                updated = {
                    'name': _val(form, 'name'),
                    'description': _val(form, 'description'),
                    'model': _val(form, 'model', 'nano-banana-pro-preview'),
                    'profile': _val(form, 'profile', 'ketose'),
                    'aspect_ratio': _val(form, 'aspect_ratio', '1:1'),
                    'count': int(_val(form, 'count', '1')),
                    'prompt': _val(form, 'prompt'),
                    'output_name_pattern': _val(form, 'output_name_pattern'),
                    'purge_existing_outputs': _val(form, 'purge_existing_outputs') == 'on',
                }
                ref = _val(form, 'ref_image')
                if ref:
                    updated['ref_image'] = ref
                _save_preset(preset_path, updated)
                data = _load_preset(preset_path)
                alert = f'저장 완료: {preset_path.name}'
            except Exception as e:
                alert = f'저장 실패: {e}'

        elif action == 'normalize':
            ok, msg = _run_normalizer()
            data = _load_preset(preset_path)
            alert = ('정규화 완료\n' + msg) if ok else ('정규화 실패\n' + msg)

        elif action == 'run':
            ok, logs, media_paths = _run_preset(preset_name)
            alert = ('결과: 생성 성공\n' if ok else '결과: 생성 실패\n') + '실행 로그:\n' + logs
            allowed_ids = {cid for cid, _ in _discord_publish_channel_options()}
            cid = _val(form, 'publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID)
            if ok and media_paths and cid and cid in allowed_ids:
                with_caption = (_val(form, 'upload_with_caption') == 'on')
                up_content = ''
                if with_caption:
                    up_content = _build_upload_caption(
                        _val(form, 'prompt', str(data.get('prompt', ''))).strip(),
                        _val(form, 'model', str(data.get('model', 'nano-banana-pro-preview'))).strip(),
                        logs,
                    )
                ok_up, msg = _upload_discord(cid, media_paths[-1], up_content)
                alert += f"\n\n업로드: {'성공' if ok_up else '실패'}\n{msg}"
            elif ok and cid:
                alert += "\n\n업로드: 허용되지 않은 채널 선택"
            data = _load_preset(preset_path)

        elif action == 'run_direct':
            ok, logs, media_paths = _run_direct(form)
            alert = ('결과: 즉시 실행 성공\n' if ok else '결과: 즉시 실행 실패\n') + '실행 로그:\n' + logs
            allowed_ids = {cid for cid, _ in _discord_publish_channel_options()}
            cid = _val(form, 'publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID)
            if ok and media_paths and cid and cid in allowed_ids:
                with_caption = (_val(form, 'upload_with_caption') == 'on')
                up_content = ''
                if with_caption:
                    up_content = _build_upload_caption(
                        _val(form, 'direct_prompt').strip(),
                        _val(form, 'direct_model', 'nano-banana-pro-preview').strip(),
                        logs,
                    )
                ok_up, msg = _upload_discord(cid, media_paths[-1], up_content)
                alert += f"\n\n업로드: {'성공' if ok_up else '실패'}\n{msg}"
            elif ok and cid:
                alert += "\n\n업로드: 허용되지 않은 채널 선택"
            data = _load_preset(preset_path) if preset_path.exists() else {}

        else:  # load
            data = _load_preset(preset_path)
            alert = f'불러옴: {preset_path.name}'

        data['_publish_channel_id'] = _val(form, 'publish_channel_id', DEFAULT_PUBLISH_CHANNEL_ID)
        data['_upload_with_caption'] = (_val(form, 'upload_with_caption') == 'on')
        data['_direct_prompt'] = _val(form, 'direct_prompt')
        data['_direct_model'] = _val(form, 'direct_model', 'nano-banana-pro-preview')
        data['_direct_profile'] = _val(form, 'direct_profile', 'ketose')
        data['_direct_aspect_ratio'] = _val(form, 'direct_aspect_ratio', '1:1')
        data['_direct_count'] = _val(form, 'direct_count', '1')
        data['_direct_name_pattern'] = _val(form, 'direct_name_pattern', 'direct_image_{n}.jpg')
        data['_direct_purge'] = (_val(form, 'direct_purge') == 'on')
        self._send(_form(preset_name, data, alert), 200)


def main() -> int:
    ap = argparse.ArgumentParser(description='Image Preset Web UI')
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8791)
    ap.add_argument('--auto-portproxy', action='store_true', help='WSL->Windows portproxy auto setup (best effort)')
    args = ap.parse_args()

    if args.auto_portproxy:
        ok, msg = _try_auto_port_proxy(args.port)
        print(msg if ok else f'[portproxy] {msg}')

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    ip = _local_ip()
    print(f'PRESET_WEBUI:http://127.0.0.1:{args.port}')
    print(f'PRESET_WEBUI_LAN:http://{ip}:{args.port}')
    server.serve_forever()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
