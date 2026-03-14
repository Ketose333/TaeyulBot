# policy/ops.md — 점검/크론 운영 정책 단일본

## 점검 원칙
- 단일 툴 타임아웃만으로 실패를 단정하지 않는다.
- 최종 결론은 `lastRunAt`/runs의 완료 상태를 확인한 뒤 보고한다.
- 사용자 보고에서 실행 계층 문구(예: "트리거 실패")를 직접 노출하지 않는다.
- Discord DM `일괄삭제`는 가능한 큰 배치로 우선 처리하고, 중간 진행 보고는 생략하며 종료 후 1회만 짧게 보고한다.
- Discord DM 제약으로 상대 메시지 삭제가 불가한 경우, 지울 수 있는 범위(내 메시지) 전량 처리 후 제약 사실만 1줄로 알린다.

## 일일 점검
- 09:30: 컨텍스트 위생 점검(정리 + 이상 징후 확인)
- 현재 12:00 `daily-ops-checkin-1200` 크론은 미운영 상태로 본다. 관련 규칙은 복구 전까지 활성 기준으로 취급하지 않는다.
- 7일 연속 무이상 항목은 주 1회 샘플링으로 전환하고 재발 시 일일 점검으로 복귀한다.

## 조용시간(대화/크론)
- 04:00~08:00(KST): 크론 작업만 중지, 일반 대화는 유지한다.
- 조용시간 자동화는 `cron-quiet-window-disable-0400`/`cron-quiet-window-enable-0800` 작업으로 활성 작업 상태를 저장/복구해 관리한다.

## 09:30 실행 순서 (daily-context-checklists-0930)
1. `memory/global-context.md` + `memory/channels/*.md`에서 완료된 임시 항목/중복 문장을 정리한다.
2. 전역 요약은 3줄 이내로 유지한다.
3. `memory/*.md` 데일리 로그 전체를 점검해 구형/중복 항목을 정리한다.
4. 체크리스트 문서(`policy/qa_checklist.md`/`policy/studio.md`/`studio/dashboard/config/pinned_message.md`)를 점검해 09:30 범위와 충돌/중복이 없는지 확인한다.
5. 보호 섹션(`DM_CANONICAL_POLICY`/`IMPORT_FROM_CHANNELS`/`EXPORT_TO_ALL_CHANNELS`/`DM_SYNC_EXPORT`)은 삭제·개명하지 않는다.
6. 문체 정리(허용 범위 내)만 수행하고 의미/수치/경로/명령어/ID는 변경하지 않는다.
7. 대시보드 점검 항목(`cron_health`/`youtube_state`/`dm_sync`/`quiet_window`/`rp_health`/`studio_ui_health`)은 09:30에서 중복 점검하지 않는다.
8. 변경이 있으면 1줄 보고, 없으면 `NO_REPLY`.

## 현재 슬림 체크리스트
- 대시보드 점검 항목의 단일 소스는 [`studio/dashboard/config/dashboard_checks.json`](../studio/dashboard/config/dashboard_checks.json)으로 관리한다.
- 임계치/판정값 단일 소스는 [`studio/dashboard/config/thresholds.json`](../studio/dashboard/config/thresholds.json)으로 관리한다.
- 정책 문서에는 점검 원칙만 유지하고, 개별 항목/라벨/임계치는 대시보드 설정 파일에서만 갱신한다.
- 현재 기본 점검 셋은 `cron_health`, `youtube_state`, `dm_sync`, `quiet_window`, `rp_health`, `studio_ui_health`다.

## YouTube Watch 파일 경로 단일화
- 채널 state는 `memory/youtube-watch-*.json`만 사용한다.
- 실행 요약 산출물은 `memory/.youtube_watch_last_result.json`, `memory/.youtube_watch_run_result.json`만 사용한다.
- `tmp/` 하위 임시 산출물 생성은 금지한다.
- 금지 경로/패턴:
  - `tmp/youtube_watch*.json`
  - `tmp_youtube_watch*.json`
  - `memory/youtube-watch-last-run.json` (구형)
  - `memory/youtube-watch-run-result.json` (구형)
  - 루트/임의 경로의 `youtube_watch_run*.json`, `youtube_watch_last*.json` (표준 경로 외)
  - 표준 허용 경로는 `memory/.youtube_watch_last_result.json`, `memory/.youtube_watch_run_result.json`만 인정
- 경로 위반 파일이 생기면 다음 점검 턴에 즉시 삭제하고, 표준 파일만 유지한다.

## 런타임 락 경로 단일화
- Discord bulk-delete runtime lock 단일 경로는 `studio/dashboard/runtime/discord_bulk_delete_runtime.lock`이다.
- `(구형 runtime lock 경로)`는 구형 경로로 간주하고 재생성하지 않는다.

## 09:30 안전 제한
- 허용: 문체/맞춤법/구두점/따옴표 통일, 중복 표현 압축
- 금지: 규칙 의미, 수치/시간/경로/명령어/ID 변경
- 금지: 파일명 케이스 변경/리네임(사용자 명시 지시가 있을 때만 수동 수행)
- 모호하면 원문 유지

## 컨텍스트 동기화 운영
- DM -> 채널 동기화 소스는 [`memory/channels/discord_dm_ketose.md`](../memory/channels/discord_dm_ketose.md)의 `## EXPORT_TO_ALL_CHANNELS`를 우선한다.
- `## EXPORT_TO_ALL_CHANNELS`가 없으면 같은 파일의 `## DM_CANONICAL_POLICY (authoritative)`를 사용한다.
- 채널 -> DM 반영은 각 채널 파일의 `## EXPORT_TO_DM`에서 `[RULE]/[DECISION]/[FAILURE]` 태그 항목만 반영한다.
- 보호 섹션(`DM_CANONICAL_POLICY`/`IMPORT_FROM_CHANNELS`/`EXPORT_TO_ALL_CHANNELS`/`DM_SYNC_EXPORT`)은 자동 정리 대상에서 제외한다.
