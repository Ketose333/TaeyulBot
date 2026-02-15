쇼츠 생성 파이프라인 정리 (Python 기준 최신)

위치
- `/home/user/.openclaw/workspace/studio/shorts_pipeline.py`
- `/home/user/.openclaw/workspace/studio/shorts_webui.py` (로컬 조정 UI)

Web UI(v1)
```bash
python3 /home/user/.openclaw/workspace/studio/shorts_webui.py --host 127.0.0.1 --port 8787 --mode ui

# UI 없이 defaults로 즉시 렌더(+옵션 시 디스코드 업로드)
python3 /home/user/.openclaw/workspace/studio/shorts_webui.py --mode run
```

- 접속: `http://127.0.0.1:8787`
- 필수 입력: `title`, `lines`, `out`
- `voice`/`font`/`caption_font`는 드롭다운으로 선택
- 이미지 소스는 체크박스로 선택(`web` 기본 / `ai` 보조)
- `나무위키 우선`/`디시인사이드 우선` 옵션은 웹 검색 키워드 가중치로 사용(둘 다 켜면 동등 참고)
- 웹 이미지 수집이 실패하면 범용 이미지를 쓰지 않고, 작업별 `fallback_channel_id`로 YouTube 이미지를 안전 fallback으로 사용
- 운영 원칙: Web 우선 시도 → 실패/품질 저하 시 YouTube fallback → AI는 옵션 ON일 때만 보조 사용
- AI 소스 사용 시 최소 3장 자동 생성 후 모두 후보 이미지로 투입 (`ai_image_count`, 최소 3)
- TTS 사용 토글 제공(환경에서 TTS 사용 불가로 판단되면 기본 OFF)
- TTS OFF여도 실행 가능(무음 placeholder 오디오로 레이아웃 테스트)
- 기본 동작: 실행 전 기존 산출물(out/cache/frames) 자동 삭제, 필요 시 `--keep-existing`로 유지
- `short_name`만 바꾸면 lines/subs/out 기본 경로를 자동 채움(기본 운영)
- 좌표/레터박스(`title_y`, `subtitle_y`, `caption_y`, `top_h`, `bottom_h`) 즉시 조정 가능
- 실행 성공 시 에러로그(stderr)는 숨김, 실패 시에만 상세 로그 표시
- UI에서 `publish_channel_id`를 넣으면 렌더 성공 직후 해당 디스코드 채널로 mp4 업로드

연관 스크립트
- `/home/user/.openclaw/workspace/studio/gemini_tts.py`
- `/home/user/.openclaw/workspace/studio/gemini_image.py`
- `/home/user/.openclaw/workspace/studio/gemini_veo.py`

보이스 규칙
- 쇼츠: `Charon`
- 비쇼츠 TTS: `Fenrir` (차분 톤 기본)

동작 구조
1) 이미지 수집
- 웹 키워드(`web_query`) 기반으로 위키/커먼즈 계열의 신뢰 소스 이미지 자동 수집
- `extra_image_url`로 수동 URL을 추가 병합 가능(여러 URL 가능)
- AI 옵션이 켜진 경우에만 보조/대체 이미지 생성

2) TTS 청크 생성
- `--lines` 파일(줄 단위)을 읽어서 문장별 오디오 생성
- `--subs` 생략 시 `--lines`를 자막으로 그대로 사용 (중복 텍스트 파일 생성 최소화)
- 내부적으로 `gemini_tts.py` 호출 (`c01.wav`, `c02.wav` ...)
- 동일 문장/보이스는 실행 내 중복 생성 방지 + 전역 TTS 캐시(`media/.cache_tts_global/`) 재사용으로 쿼터 절약

3) 청크 오디오 스티칭
- WAV들을 순서대로 합치고 각 문장 길이(초) 계산

4) 렌더링
- 1080x1920 캔버스
- 상/하단 레터박스 + 중앙 이미지 영역
- 기본은 레터박스 우선 자동 텍스트 배치
- 레터박스 기본값 고정: `top-h=600`, `bottom-h=600` (쇼츠 간 일관성 유지)
- 문장 길이 기반 컷 duration으로 자막/오디오 싱크 유지

5) BGM 믹싱 (선택)
- 기본 BGM: `/home/user/.openclaw/workspace/media/bgm/bgm_full.mp3`
- `--bgm ""`로 비활성화 가능

6) 결과 첨부 (운영 규칙)
- 렌더가 끝나면 결과 MP4를 해당 디스코드 채널에 즉시 첨부
- 같은 규칙을 이미지/TTS/영상 산출물에도 동일 적용
- 생성 성공 + 채널 첨부 완료를 최종 완료 기준으로 본다
- 업로드 경로가 거절되면 임시 허용 경로로 복사 후 첨부(예: `/tmp/tts-d5qKz5/`)

주요 옵션
- 필수: `--title`, `--lines`, `--out` (`--subs`는 선택)
- 이미지 수집: `--skip-youtube`, `--extra-image-url`(복수), `web_query`(UI)
- TTS: 기본 생성 / `--no-tts` 무음 테스트 / `--tts-placeholder-seconds` 길이 조정
- 레이아웃: `--top-h`, `--bottom-h`, `--subtitle-y-offset`, `--caption-font`, `--caption-y-offset`, 수동 y값들(`--title-y`, `--subtitle-y`, `--caption-y`)
- 하단 캡션은 `...`를 출력하지 않음 (줄 수 초과 시 내부 축약 + 균등 재분배 후 1~3줄 유지)
- 캐시: `--cache-key`, `--no-reuse`
- 보존 옵션: `--keep-existing` (기존 산출물 삭제 비활성화)
- 정리: `--cleanup-temp`

실행 예시
```bash
python3 /home/user/.openclaw/workspace/studio/shorts_pipeline.py \
  --skip-youtube \
  --extra-image-url "https://upload.wikimedia.org/.../example.jpg" \
  --title "Camellia 소개" \
  --subtitle "작곡가 프로필" \
  --font /home/user/.openclaw/workspace/fonts/SBAggroB.ttf \
  --lines /home/user/.openclaw/workspace/examples/camellia_lines.txt \
  --subs /home/user/.openclaw/workspace/examples/camellia_subs.txt \
  --out /home/user/.openclaw/workspace/output/camellia-intro-shorts-sync-v2.mp4
```

주의
- `--lines`와 `--subs` 줄 수는 반드시 같아야 함
- `--subs`에서 줄바꿈은 `\n`으로 입력
- 한글 폰트 경로가 틀리면 글자 깨짐 발생


내부 최적화(출력 결과 동일 목표)
- 캡션 줄바꿈 함수의 도달 불가(dead) 코드 제거로 실행 경로 단순화
- TTS 청크 생성 후 파일 존재/용량 검증 추가(실패 조기 감지)
- `--extra-image-file` 입력 중복 경로는 1회만 사용해 불필요 I/O 감소
- 위 최적화는 동일 입력에서 시각/오디오 결과를 바꾸지 않는 범위로 적용

- 하단 자막 알고리즘: 기본 18자 폭으로 시작하되, 3줄 초과 시 폭을 점진 확장해 원문 tail-cut 없이 1~3줄 내에 수용


TTS 쿼터 최적화
- 같은 문장을 여러 컷에서 반복하면 1회만 생성 후 재사용
- 이전 런에서 생성된 동일 문장/보이스 WAV는 전역 캐시에서 복사 사용
- `--no-reuse`일 때만 캐시를 무시하고 신규 생성
