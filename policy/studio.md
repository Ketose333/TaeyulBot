# policy/studio.md — 이미지/쇼츠 운영 정책 단일본

## 단일 소스
- 이미지 생성/품질 판정 기준은 [`studio/image/rules/image_rules.md`](../studio/image/rules/image_rules.md)를 따른다.

## 기본 운영
- 기본 저장/첨부/파일명 정책은 [`policy/media.md`](./media.md)를 따른다.
- 이미지 모델 기본값은 `nano-banana-pro-preview`를 사용한다.
- `nano-banana-pro-preview` 실패 시 `gemini-2.5-flash-image`로 자동 fallback한다.
- 비율 명시가 없으면 기본 생성 비율은 `1:1`로 사용한다.
- 생성 실패 시 프롬프트/모델은 한 번에 한 요소만 조정한다.
- 모델 우선순위 혼선이 생기면 `openai-codex/gpt-5.3-codex`를 우선 기준으로 확인/복구한다.
- fallback 전환 기준은 아래 순서를 고정한다:
  1) Web 수집 성공 + 품질 기준 통과 → Web 사용 유지
  2) Web 수집 실패 또는 품질 기준 미달 → YouTube fallback
  3) YouTube도 실패/품질 미달이고 AI 옵션이 ON일 때만 AI 보조 사용

## UI 통합 수칙 (신규 UI 공통)
- 새 UI는 기존 UI와 동일한 입력/결과 메커니즘을 우선 재사용한다(동일 기능 중복 구현 금지).
- 업로드 대상 선택은 공통 allowlist([`studio/publish_channels_allowlist.json`](../studio/publish_channels_allowlist.json))를 사용한다.
- 업로드 동작은 "채널 선택 = 자동 업로드"로 통일하고, 별도 체크박스 게이트를 추가하지 않는다.
- 결과 표시 포맷은 `결과:` + `실행 로그:` 구조를 기본으로 통일한다.
- 파일명 규칙은 [`policy/media.md`](./media.md)의 언더스코어 슬러그(`<topic>_<variant>.<ext>`)를 따른다.
- 로컬 실행/재기동은 통합 런타임([`studio/ui_runtime.py`](../studio/ui_runtime.py))으로 관리한다.
- 기능 확장은 기본적으로 비활성/옵션으로 추가하고, 기존 UX/기능 기본값을 깨지 않는다.

## 쇼츠
- 레터박스 기본값은 `top-h=600`, `bottom-h=600`을 유지한다.
- 이미지 소스는 Web 우선, 실패/품질 저하 시 YouTube fallback, AI는 옵션 ON일 때만 보조로 사용한다.
- 작업 흐름은 "초안 작성 → UI 미세조정 → 렌더" 순서를 유지한다.
- 운영 흐름은 "내가 제목/부제목 초안 작성 → 승세가 UI 최종 수치/문구 미세조정 → 렌더" 순서를 기본으로 한다.
- UI 실행 전 [`studio/shorts/defaults.json`](../studio/shorts/defaults.json) 입력값(주제/경로)을 먼저 합의한다.
- `lines`/`subs` 파일은 defaults와 같은 턴에 함께 갱신한다.
- 렌더 직전 워터마크 이미지 사용 여부를 중간 점검하고, 워터마크 소스는 기본 제외한다.
- 별도 점검 스크립트가 없어도 위 합의/점검 절차를 수동 체크리스트로 동일 적용한다.
