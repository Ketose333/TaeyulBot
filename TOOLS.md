# TOOLS.md — 로컬 도구/환경 메모

이 문서는 **공유 스킬 문서가 아닌, 현재 로컬 환경 전용 메모**를 기록한다.
원칙/정책은 [`AGENTS.md`](./AGENTS.md), [`MEMORY.md`](./MEMORY.md), [`policy/*.md`](./policy/)를 우선한다.

## 목적
- 장비/경로/이름처럼 환경 의존 정보의 단일 메모
- 세션이 바뀌어도 같은 실행 품질을 유지하기 위한 체크포인트
- 스킬 문서와 분리해 업데이트 충돌을 줄임
- 설치/사용 스킬 목록은 [`SKILLS.md`](./SKILLS.md)에서 관리

## 현재 로컬 고정값

### 작업 루트
- Workspace: `/home/user/.openclaw/workspace`
- Media root: `/home/user/.openclaw/media`

### Python/venv
- 활성화: `source .venv/bin/activate`
- 종료: `deactivate`

### TTS
- 기본 보이스 정체성: `Fenrir` (한태율 기본 목소리)

### Studio UI 포트
- Cron UI: `8767`
- Shorts UI: `8787`
- Image UI: `8791`

### 네트워크/포트포워딩
- Windows/WSL portproxy 갱신 스크립트: [`utility/common/windows_wsl_portproxy_autoupdate.ps1`](./utility/common/windows_wsl_portproxy_autoupdate.ps1)
- 참고 문서: [`utility/common/README.md`](./utility/common/README.md)

## 작성 규칙
- 이 문서에는 **환경 사실**만 기록한다.
- 정책/행동 규칙은 이 문서에 중복 기록하지 않는다(해당 문서 링크만 둔다).
- 값이 바뀌면 같은 턴에 즉시 갱신한다.
- 민감정보(토큰/비밀번호/개인키)는 기록하지 않는다.

## 추가 후보 항목(필요 시)
- 카메라 이름/위치
- 자주 쓰는 채널 ID 이름
- 장치별 오디오/마이크 이름
- SSH 호스트 이름
