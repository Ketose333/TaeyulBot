# Utility Directory Guide

`utility/` 하위 폴더 용도 요약:

- `common/` : 공용 헬퍼/시스템 유틸
  - 예: `windows_audio_mute.*` 관련 문서
- `discord/` : 디스코드 전용 유틸/가이드
  - 예: `discord_bulk_delete.py`, `BULK_DELETE_PIPELINE.md`
- `logs/` : 유틸 실행 로그/중간 로그 파일 자리

구조 의도:
- 디스코드 특화 기능은 `discord/`로 모으고,
- 채널 비종속 공용 기능은 `common/`으로 모은다.
