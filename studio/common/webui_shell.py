from __future__ import annotations

import html

# Studio webui 공통 셸 스타일
# - dashboard 제외 webui(shorts/image/music) 공통 적용
# - 페이지별 예외는 각 webui에서 class 추가로만 처리
COMMON_STYLE = """
:root {
  --bg: #0b1020;
  --card: #131a2d;
  --line: #2a3658;
  --text: #e8ecff;
  --muted: #9fafd9;
  --accent: #2aa748;
  --accent2: #4f8cff;

  --c-page-base: #0b1020;
  --c-intro-panel: rgba(79, 140, 255, 0.14);
  --grid-line: rgba(255, 255, 255, 0.045);
  --grid-size: 22px;

  --c-surface-1: rgba(19, 26, 45, 0.92);
  --c-accent-blue-wash-14: rgba(79, 140, 255, 0.14);
}

* {
  box-sizing: border-box;
}

html,
body {
  max-width: 100%;
  overflow-x: hidden;
  min-height: 100vh;
  min-height: 100dvh;
}

body {
  margin: 0;
  color: var(--text);
  font-family: Inter, Segoe UI, Arial, sans-serif;
  background: var(--c-page-base);
  position: relative;
}

/* TCG 쪽 배경 톤 차용: viewport 고정 그리드 + 워시 */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: -2;
  background:
    radial-gradient(1400px 860px at 14% 10%, var(--c-intro-panel) 0%, transparent 56%),
    radial-gradient(1400px 880px at 86% 90%, var(--c-intro-panel) 0%, transparent 58%),
    repeating-linear-gradient(0deg, var(--grid-line) 0 1px, transparent 1px var(--grid-size)),
    repeating-linear-gradient(90deg, var(--grid-line) 0 1px, transparent 1px var(--grid-size)),
    linear-gradient(180deg, var(--c-page-base) 0%, var(--c-page-base) 100%);
}

.app-shell {
  max-width: 1040px;
  margin: 26px auto;
  padding: 0 18px;
}

h2 {
  margin: 0 0 10px 0;
  font-size: 24px;
  letter-spacing: 0.2px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.desc {
  display: none;
}

.section {
  min-width: 0;
  margin: 14px 0;
  padding: 16px 16px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.16);
  background:
    linear-gradient(145deg, var(--c-accent-blue-wash-14) 0%, transparent 26%),
    linear-gradient(180deg, var(--c-surface-1), var(--c-surface-1));
}

.section h3 {
  margin: 0 0 10px 0;
  font-size: 15px;
  color: #d8e2ff;
  overflow-wrap: anywhere;
  word-break: break-word;
}

label {
  display: block;
  margin-top: 12px;
  margin-bottom: 7px;
  font-size: 13px;
  font-weight: 600;
  color: #d7e0ff;
}

input,
select,
button {
  width: 100%;
  height: 40px;
  line-height: 1.2;
  padding: 8px 12px;
  border: 1px solid #3a4a79;
  border-radius: 10px;
  background: #0f1527;
  color: var(--text);
}

textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #3a4a79;
  border-radius: 10px;
  background: #0f1527;
  color: var(--text);
}

input::placeholder,
textarea::placeholder {
  color: #9fafd9;
}

input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: var(--accent2);
  box-shadow: 0 0 0 2px rgba(79, 140, 255, 0.2);
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  align-items: start;
}

.row-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
  align-items: start;
}

.row > div,
.row-3 > div {
  min-width: 0;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.action-row button {
  width: auto;
  min-width: 128px;
}

.checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  margin-bottom: 2px;
  font-size: 13px;
  line-height: 1.25;
  font-weight: 500;
  color: #d7e0ff;
}

.checkline + .checkline {
  margin-top: 2px;
}

.checkline input {
  width: auto;
  height: 14px;
  min-height: 14px;
  margin: 0;
}

.msg {
  margin-top: 8px;
  font-size: 13px;
  color: #9fafd9;
}

.textarea-compact {
  min-height: 120px;
  resize: vertical;
}

.code-editor {
  min-height: 280px;
}

button {
  margin-top: 0;
  min-height: 40px;
  padding: 8px 12px;
  border: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(90deg, var(--accent), #2fd37c);
}

button.secondary,
button.sub {
  color: #d7e0ff;
  border: 1px solid #3a4a79;
  background: #1f2b47;
}

pre {
  white-space: pre-wrap;
  overflow: auto;
  padding: 12px;
  border: 1px solid #2d3a61;
  border-radius: 10px;
  background: #0c1222;
  color: #d7e0ff;
}

.hint {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}

.state-ok {
  color: #7dffa2;
}

.state-warn {
  color: #ff9f7a;
}

.state-error {
  color: #ff7777;
}

.badges,
.badge {
  display: none;
}

.alert {
  padding: 10px;
  border: 1px solid #2aa748;
  border-radius: 10px;
  background: #133222;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 780px) {
  .app-shell {
    padding: 0 12px;
  }

  .row,
  .row-3 {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  input,
  textarea,
  select,
  button {
    font-size: 16px;
  }
}
"""


def render_page(
    *,
    title: str,
    heading: str,
    desc: str = '',
    badges: list[str] | None = None,
    body_html: str = '',
    extra_style: str = '',
) -> bytes:
    # 하위 호환용 파라미터(desc/badges/extra_style)는 유지
    _ = desc
    _ = badges

    page = f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{html.escape(title)}</title>
<style>{COMMON_STYLE}\n{extra_style}</style></head><body>
<div class='app-shell'>
<h2>{html.escape(heading)}</h2>
{body_html}
</div>
</body></html>"""
    return page.encode('utf-8')
