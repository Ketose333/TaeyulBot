# Channel Memory

채널별 진행상황/결정사항만 기록.

규칙
- 개인 정보/전역 규칙은 MEMORY.md에 기록
- 채널 메모는 해당 채널의 작업 문맥만 유지
- 완료된 임시 이슈는 주기적으로 삭제/압축
- DM -> 채널: `discord_dm_ketose.md`의 `## EXPORT_TO_ALL_CHANNELS`만 소스로 사용
- 채널 -> DM: 각 채널 파일의 `## EXPORT_TO_DM`에서 `[RULE]/[DECISION]/[FAILURE]` 태그 항목만 반영
- 동기화 실행:
  - `python3 utility/context/sync_dm_rules.py`
  - `python3 utility/context/sync_channel_to_dm.py`
파일 예시
- `discord_dm_1470802274518433885.md`
- `discord_g953572256083218452_c1091266692857991179.md`
