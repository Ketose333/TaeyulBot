# Channel Memory

채널별 진행상황/결정사항만 기록한다.

## 범위
- 개인 정보/전역 규칙은 [`MEMORY.md`](../../MEMORY.md)에 기록한다.
- 동기화 정책의 단일본은 [`policy/ops.md`](../../policy/ops.md)다.
- 이 디렉터리는 채널별 작업 문맥/진행상황만 유지한다.

## 운영
- 완료된 임시 이슈는 주기적으로 삭제/압축한다.
- 동기화 실행:
  - `python3 utility/context/sync_dm_rules.py`
  - `python3 utility/context/sync_channel_to_dm.py`

## 파일 예시
- [`discord_dm_ketose.md`](./discord_dm_ketose.md)
- [`discord_g1155399929787846748_c1471931748194455807.md`](./discord_g1155399929787846748_c1471931748194455807.md)
