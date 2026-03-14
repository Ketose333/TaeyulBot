#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.bootstrap import ensure_workspace_imports
ensure_workspace_imports(__file__)
from common.webui_shell import render_page

try:
    from utility.common.generation_defaults import MEDIA_ROOT, WORKSPACE_ROOT
    from utility.common.studio_ui_common import load_publish_channel_options
except ModuleNotFoundError:
    ensure_workspace_imports(__file__)
    from utility.common.generation_defaults import MEDIA_ROOT, WORKSPACE_ROOT
    from utility.common.studio_ui_common import load_publish_channel_options

WORKSPACE = WORKSPACE_ROOT
PRESETS_PATH = WORKSPACE / 'studio' / 'music' / 'strudel_presets.json'
DEFAULT_PUBLISH_CHANNEL_ID = '1470802274518433885'


def _local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()
STRUDEL_WAV_DIRS = [
    (MEDIA_ROOT / 'audio' / 'strudel').resolve(),
    (MEDIA_ROOT / 'bgm' / 'strudel').resolve(),
]


def _discord_publish_channel_options() -> list[tuple[str, str]]:
    return load_publish_channel_options(WORKSPACE, DEFAULT_PUBLISH_CHANNEL_ID)


def _latest_strudel_wav() -> Path | None:
    files: list[Path] = []
    for root in STRUDEL_WAV_DIRS:
        if root.exists():
            files.extend([p for p in root.glob('*.wav') if p.is_file()])
    if not files:
        return None
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0]


def _publish_latest_wav_to_discord(channel_id: str) -> tuple[bool, str]:
    cid = (channel_id or '').strip()
    if not cid or not cid.isdigit():
        return False, '채널 ID가 올바르지 않아'

    target = _latest_strudel_wav()
    if not target:
        return False, 'Strudel 생성 wav가 없어. 먼저 렌더/저장부터 해줘'

    py = str(WORKSPACE / '.venv' / 'bin' / 'python3') if (WORKSPACE / '.venv' / 'bin' / 'python3').exists() else 'python3'
    cmd = [
        py,
        str(WORKSPACE / 'utility' / 'discord' / 'discord_send_media.py'),
        '--channel-id', cid,
        '--file', str(target),
        '--content', f'Strudel wav 배포: {target.name}',
    ]
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
    if p.returncode == 0:
        return True, (p.stdout or f'배포 완료: {target.name}').strip()
    return False, (p.stderr or p.stdout or '배포 실패').strip()


DEFAULT_PRESETS = {
    'city-night-house': 'stack(s("bd*4").gain(1.1), s("~ sd ~ sd").gain(0.85), s("hh*8").gain(0.35)).slow(1)',
    'warm-rnb-loop': 'stack(s("bd [~ bd] bd ~").gain(1.0), s("~ ~ sd ~").gain(0.7), s("hh*8").degradeBy(0.2).gain(0.28)).slow(1.05)',
}


def _load_presets() -> dict[str, str]:
    if not PRESETS_PATH.exists():
        PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRESETS_PATH.write_text(json.dumps(DEFAULT_PRESETS, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return dict(DEFAULT_PRESETS)
    try:
        data = json.loads(PRESETS_PATH.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if str(k).strip()}
    except Exception:
        pass
    return dict(DEFAULT_PRESETS)


def _save_presets(presets: dict[str, str]) -> None:
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_PATH.write_text(json.dumps(presets, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _page(body: str) -> bytes:
    return render_page(
        title='Music UI',
        heading='뮤직 생성 UI',
        body_html=body,
    )


def _form(presets: dict[str, str]) -> str:
    presets_json = json.dumps(presets, ensure_ascii=False)
    publish_options = _discord_publish_channel_options()
    publish_html = ''.join(
        f'<option value="{html.escape(cid)}">{html.escape(label)}</option>'
        for cid, label in publish_options
    )

    return f'''
<div class="section">
  <h3>기본 제어</h3>
  <div class="row-3">
    <div>
      <label>프리셋 선택</label>
      <select id="preset"></select>
    </div>
    <div>
      <label>재생</label>
      <button type="button" id="play">Play</button>
    </div>
    <div>
      <label>정지</label>
      <button type="button" class="sub" id="stop">Stop</button>
    </div>
  </div>
  <div id="msg" class="msg">ready</div>
</div>

<div class="section">
  <h3>프리셋 관리</h3>
  <div class="row">
    <div>
      <label>프리셋 이름</label>
      <input id="newName" placeholder="예: melodic-rush" />
    </div>
    <div>
      <label>저장</label>
      <button type="button" id="upsertPreset">새로 만들기/현재 저장</button>
    </div>
  </div>
  <label>코드 편집</label>
  <textarea id="code" class="code-editor"></textarea>
</div>

<div class="section">
  <h3>저장 경로</h3>
  <pre>{html.escape(str(PRESETS_PATH))}</pre>
  <pre id="lastSavedWav">최근 저장 wav: (없음)</pre>
</div>

<div class="section">
  <h3>배포</h3>
  <label>publish_channel_id</label>
  <select id="publishChannel">{publish_html}</select>
</div>

<button type="button" id="runNow">즉시 실행</button>

<script src="https://unpkg.com/@strudel/web@1.3.0"></script>
<script>
let presets = {presets_json};
if (!presets || typeof presets !== 'object') presets = {{}};
const sel = document.getElementById('preset');
const code = document.getElementById('code');
const msg = document.getElementById('msg');
const lastSavedWav = document.getElementById('lastSavedWav');

function setMsg(text, bad=false) {{
  msg.style.color = bad ? '#ff9f7a' : '#9fafd9';
  msg.textContent = text;
}}

function renderList() {{
  const prev = sel.value;
  sel.innerHTML = '';
  Object.keys(presets).forEach((k) => {{
    const o = document.createElement('option');
    o.value = k; o.textContent = k; sel.appendChild(o);
  }});
  if (prev && presets[prev]) sel.value = prev;
  if (!sel.value && sel.options.length) sel.value = sel.options[0].value;
  code.value = presets[sel.value] || '';
}}

sel.addEventListener('change', () => {{
  code.value = presets[sel.value] || '';
  setMsg(`선택: ${{sel.value}}`);
}});
renderList();

let inited = false;
async function init() {{
  if (!inited) {{
    await initStrudel();
    inited = true;
  }}
}}

async function playNow() {{
  try {{
    await init();
    if (window.Tone && typeof window.Tone.start === 'function') {{ try {{ await window.Tone.start(); }} catch (_) {{}} }}
    if (window.audioContext && typeof window.audioContext.resume === 'function') {{ try {{ await window.audioContext.resume(); }} catch (_) {{}} }}
    // eslint-disable-next-line no-eval
    eval(`${{code.value}}.play()`);
    setMsg('재생 중');
  }} catch (e) {{
    setMsg('실행 오류: ' + e.message, true);
  }}
}}

function stopNow() {{
  try {{
    if (typeof hush === 'function') hush();
    setMsg('정지');
  }} catch (e) {{
    setMsg('정지 오류: ' + e.message, true);
  }}
}}

async function runNow() {{
  try {{
    const body = new URLSearchParams();
    body.set('channel_id', document.getElementById('publishChannel').value || '');
    const r = await fetch('/publish-wav', {{
      method:'POST',
      headers:{{'content-type':'application/x-www-form-urlencoded'}},
      body,
    }});
    const data = await r.json();
    if (!data.ok) return setMsg('배포 실패: ' + (data.error || ''), true);
    setMsg('배포 완료: ' + (data.message || 'ok'));
    if (data.path && lastSavedWav) lastSavedWav.textContent = '최근 저장 wav: ' + data.path;
  }} catch (e) {{
    setMsg('배포 오류: ' + e.message, true);
  }}
}}

document.getElementById('play').addEventListener('click', playNow);
document.getElementById('stop').addEventListener('click', stopNow);
document.getElementById('runNow').addEventListener('click', runNow);

document.getElementById('upsertPreset').addEventListener('click', async () => {{
  try {{
    const name = (document.getElementById('newName').value || sel.value || '').trim();
    if (!name) return setMsg('프리셋 이름을 입력해줘', true);

    presets[name] = code.value || '';
    renderList();
    sel.value = name;

    const body = new URLSearchParams();
    body.set('presets_json', JSON.stringify(presets));
    const r = await fetch('/save', {{
      method:'POST',
      headers:{{'content-type':'application/x-www-form-urlencoded'}},
      body,
    }});
    const data = await r.json();
    if (!data.ok) return setMsg('저장 실패: ' + (data.error || ''), true);
    setMsg('저장 완료: ' + name);
  }} catch (e) {{
    setMsg('저장 오류: ' + e.message, true);
  }}
}});
</script>
'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str | bytes, ctype: str = 'text/html; charset=utf-8') -> None:
        b = body if isinstance(body, (bytes, bytearray)) else body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        if self.path != '/':
            self._send(404, 'not found', 'text/plain; charset=utf-8')
            return
        self._send(200, _page(_form(_load_presets())))

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length', '0') or 0)
        raw = self.rfile.read(length).decode('utf-8', errors='replace')
        form = parse_qs(raw)

        if self.path == '/save':
            try:
                payload = json.loads((form.get('presets_json', ['{}'])[0] or '{}'))
                if not isinstance(payload, dict):
                    raise ValueError('invalid payload')
                presets = {str(k): str(v) for k, v in payload.items() if str(k).strip()}
                _save_presets(presets)
                self._send(200, json.dumps({'ok': True}), 'application/json; charset=utf-8')
            except Exception as e:
                self._send(400, json.dumps({'ok': False, 'error': str(e)}), 'application/json; charset=utf-8')
            return

        if self.path == '/publish-wav':
            channel_id = (form.get('channel_id', [''])[0] or '').strip()
            ok, msg = _publish_latest_wav_to_discord(channel_id)
            code = 200 if ok else 400
            path = str(_latest_strudel_wav() or '') if ok else ''
            self._send(code, json.dumps({'ok': ok, 'message': msg, 'path': path, 'error': '' if ok else msg}), 'application/json; charset=utf-8')
            return

        self._send(404, json.dumps({'ok': False, 'error': 'not found'}), 'application/json; charset=utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8795)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    ip = _local_ip()
    print(f'STUDIO_UI_MUSIC_BIND:http://{args.host}:{args.port}')
    print(f'STUDIO_UI_MUSIC_LAN:http://{ip}:{args.port}')
    httpd.serve_forever()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
