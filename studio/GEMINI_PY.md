Gemini Python 스크립트 정리

위치
- 공통 폴더: `/home/user/.openclaw/workspace/studio/`

환경 변수
- 아래 중 하나 필요
  - `GEMINI_API_KEY`
  - `GOOGLE_API_KEY`

파일별 용도

1) `gemini_tts.py`
- 텍스트를 음성으로 생성 (TTS)
- 기본 모델: `gemini-2.5-flash-preview-tts`
- 기본 보이스: `Fenrir` (비쇼츠 기본)
- 쇼츠 파이프라인 사용 시 보이스 기준: `Charon`

주요 옵션
- `--voice`
- `--out-dir`
- `--name`
- `--emit-media`

예시
```bash
python3 /home/user/.openclaw/workspace/studio/gemini_tts.py "안녕" --voice Charon --out-dir /home/user/.openclaw/workspace/output --emit-media
```

2) `gemini_image.py`
- 텍스트 프롬프트로 이미지 생성
- 기본 모델: `nano-banana-pro-preview`

주요 옵션
- `--model`
- `--out-dir`
- `--name`
- `--emit-media`

예시
```bash
python3 /home/user/.openclaw/workspace/studio/gemini_image.py "네온 사이버펑크 도시" --out-dir /home/user/.openclaw/workspace/output --emit-media
```

3) `gemini_veo.py`
- Veo 계열 모델로 영상 생성 시도 (프로젝트 권한 필요)
- 기본 모델: `models/veo-3.1-generate-preview`

주요 옵션
- `--model`
- `--out-dir`
- `--name`
- `--poll-seconds`

예시
```bash
python3 /home/user/.openclaw/workspace/studio/gemini_veo.py "9:16 우주 배경의 짧은 인트로 영상" --name intro_clip
```

운영 규칙 (완료 기준)
- 이미지(`gemini_image.py`), TTS(`gemini_tts.py`), 영상(`gemini_veo.py`) 결과물도 동일하게 완료 즉시 해당 디스코드 채널에 첨부
- 생성 성공 + 채널 첨부 완료를 최종 완료로 본다

연계
- 쇼츠 파이프라인은 `shorts_pipeline.py`에서 `gemini_tts.py`를 내부 호출함
- 상세 파이프라인 설명은 `SHORTS_PIPELINE.md` 참고


taeyul_cli.py 단축 커맨드
- `python3 /home/user/.openclaw/workspace/taeyul_cli.py tts ...`
- `python3 /home/user/.openclaw/workspace/taeyul_cli.py image ...`
- `python3 /home/user/.openclaw/workspace/taeyul_cli.py veo ...`
- `python3 /home/user/.openclaw/workspace/taeyul_cli.py shorts ...`

업로드 안전 루틴
- 로컬 `media/*` 파일이 채널 업로드 허용 경로에 바로 안 잡히는 경우가 있음
- 이때는 임시 허용 경로로 복사 후 첨부
- 예시: `cp /home/user/.openclaw/workspace/media/tts/<file>.wav /tmp/tts-d5qKz5/<name>.wav` 후 첨부
