# RP Engine (Thread-first MVP)

명령 최소화 + 제타형 사용감을 목표로 한 RP 저장 엔진 운영 가이드.

## 핵심 규칙
- 서버/그룹: **룸 = 스레드 1개**
- DM: **단일 채널 룸 1개**
- 명령어(간단형):
  - `!rp 시작 [주제]`
  - `!rp 끝`
  - `!rp 이름 <호칭>` (`!rp 이름`으로 해제)
  - `!rp 사용자명`
  - `!rp 가이드`

## 파일
- `rp_engine.py` (상태 저장 엔진)
- `studio/dashboard/actions/rp_runtime_action.py` (디스코드 연결, 대시보드 ON/OFF 전용)
- 저장 경로: `memory/rp_rooms/`
  - 룸별 JSON 1개: `<platform>_<channel>.json`
  - 룸별 로그 MD 1개: [`<platform>_<channel>.md`](../../memory/rp_rooms/)

## 동작
- 일반 서버 채널에서 `!rp 시작` 입력 시
  - 스레드를 자동 생성하고 해당 스레드를 RP 룸으로 시작한다.
- 스레드/DM 안에서 `!rp 시작` 입력 시
  - 현재 채널을 RP 룸으로 시작한다.
- `!rp 시작 <오프닝>` 지원
  - 오프닝을 첫 장면으로 저장한다.
- `!rp 끝`
  - 현재 룸을 종료한다(스레드면 자동 아카이브 시도).
  - 활성 룸 인덱스/임시 recent id/구형 캐시를 자동 정리한다.
- 일반 채팅 메시지
  - 해당 채널/스레드가 활성 RP 룸일 때만 히스토리에 저장한다.
  - 매 턴 문맥 기반으로 RP 응답을 생성한다(고정 한 줄 제거).
  - 포맷 규칙: 대사 따옴표/볼드 금지, 행동/비가시 정보는 기울임체 허용.
  - 생성 실패 시 보조 안내 문구 없이 무응답으로 처리한다.
- RP 활성 룸에서는 `!rp` 외 비RP 운영 명령에 반응하지 않는다.

## 실행
- 기본/권장: 대시보드 `운영 실행 > RP ON / RP OFF` 단일 진입점 사용
- 수동 점검이 필요할 때만 아래 헬스체크 사용
```bash
python3 utility/taeyul/taeyul_cli.py rp-healthcheck
python3 utility/taeyul/taeyul_cli.py rp-healthcheck --recover
```

## RP 전용 서브에이전트 마이그레이션 (최소 패치)

### 1) RP 모드 런타임은 대시보드에서 단일 관리
- 실행/중지는 대시보드 `RP ON / RP OFF`로만 처리
- 토큰 우선순위: `RP_DISCORD_BOT_TOKEN` → 없으면 `DISCORD_BOT_TOKEN`
- 권장: RP 전용 런타임 토큰 사용(메인과 완전 분리)

### 2) RP 채널 격리(메인 응답 차단)
- RP 채널 ID를 메인 allowlist에서 제거하고 RP 모드 런타임 허용 목록으로 이관
```bash
--rp-channel-id <RP_CHANNEL_ID>
```
- dry-run
```bash
--rp-channel-id <RP_CHANNEL_ID> --dry-run
```

### 3) 중복 응답/중복 적재 방지
- `discord_rp_runtime.py`: 메시지 ID LRU 캐시로 중복 이벤트 무시
- `rp_engine.py`: `recent_message_ids`로 중복 히스토리 적재 차단
- 런타임 락: `memory/rp_rooms/_runtime_lock.json`
  - 동일 토큰/프로세스 중복 실행 자동 차단
- 활성 룸 인덱스: `memory/rp_rooms/_active_rooms.json`

### 4) 헬스체크/런타임 복구 훅
```bash
python3 utility/taeyul/taeyul_cli.py rp-healthcheck
python3 utility/taeyul/taeyul_cli.py rp-healthcheck --recover
```
- 손상된 활성 룸 인덱스/죽은 런타임 락만 복구한다(콘텐츠 로그는 건드리지 않음).

## 테스트 절차
1. RP 채널에서 `!rp 시작` 입력
2. 같은 메시지 재전달/재시도 시 로그 중복 적재 없는지 확인
3. RP 채널에서 메인 에이전트 응답 없음 확인
4. 일반 채널에서 기존 메인 응답 유지 확인
5. 종료: `!rp 끝`

## 구형 룸 자동 청소
- 정책 상세(구형 범위/보호 규칙)는 [`policy/rp.md`](../../policy/rp.md)를 단일 기준으로 따른다.
- 실행 명령:
```bash
python3 utility/rp/rp_engine.py --cleanup-non-active
```

## 롤백 절차
- 설정 롤백: `~/.openclaw/openclaw.json.rp-backup`를 `openclaw.json`으로 복원
- 코드 롤백: git 기준
```bash
git restore studio/dashboard/actions/rp_runtime_action.py utility/rp/rp_engine.py utility/taeyul/taeyul_cli.py utility/rp/README.md
```

## 주의
- 동일 토큰으로 기존 봇 프로세스와 동시 실행하면 충돌 가능
