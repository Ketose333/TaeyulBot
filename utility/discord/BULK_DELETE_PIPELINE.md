# Discord 일괄삭제 파이프라인 (utility)

목표
- `guildId required` 같은 라우팅 이슈를 피하고, 채널 타입에 맞게 안전하게 삭제
- 기본은 미리보기(dry-run), `--execute`가 있어야 실제 삭제
- 운영 원칙: 일괄삭제 실행 후 사용자에게 `일괄삭제 완료` 같은 완료 메시지를 별도 전송하지 않음
- 유틸 기본값도 무출력(silent)이며, 필요할 때만 `--verbose`로 로그 확인

## 1) 준비

필수
- Python 3.10+
- 패키지: `discord.py`
- 환경변수: `DISCORD_BOT_TOKEN`

설치
```bash
source .venv/bin/activate
pip install discord.py
```

## 2) 실행 파일

- `utility/discord/discord_bulk_delete.py`

기본 규칙
- 최근 14일 이내 메시지: bulk delete
- 14일 초과 메시지: 개별 delete fallback
- DM 채널은 batch API 미지원이므로 개별 삭제
- 고정 메시지는 기본적으로 삭제 제외(기본값)

## 3) 사용법

미리보기(삭제 안 함)
```bash
python3 utility/discord/discord_bulk_delete.py \
  --channel-id 1470802274518433885 \
  --author-id 1146169746971451452 \
  --limit 1000
```

실행(실제 삭제)
```bash
python3 utility/discord/discord_bulk_delete.py \
  --channel-id 1470802274518433885 \
  --author-id 1146169746971451452 \
  --limit 1000 \
  --execute
```

기준 메시지 이후만
```bash
python3 utility/discord/discord_bulk_delete.py \
  --channel-id 1470802274518433885 \
  --author-id 1146169746971451452 \
  --after-message-id 123456789012345678 \
  --limit 1000 \
  --execute
```

## 4) 운영 절차(권장)

1. `--execute` 없이 대상 개수 확인
2. 필요 시 `--after-message-id`로 범위 축소
3. `--execute`로 실제 삭제
4. Rate limit 대비해서 큰 범위는 여러 번 나눠 실행

## 5) 트러블슈팅

`guildId required`
- 서버 채널 전용 경로를 DM에서 호출할 때 발생
- 이 유틸은 `fetch_channel()` 결과 타입 기준으로 분기해서 우회

`Unknown Channel`
- 채널 ID 오입력
- 봇이 해당 채널/서버에 없음
- 권한 부족(메시지 조회/삭제)

`403 Forbidden`
- 메시지 관리 권한 부족
- 타인 메시지 삭제 권한 부족

## 6) 파일 정리

이번 정리 기준
- 유틸리티성 스크립트는 `utility/` 하위에 모음
- 운영 문서도 `utility/` 하위에 함께 보관
