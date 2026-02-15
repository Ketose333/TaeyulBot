# 머슴닷컴 운영 디렉터리

이 디렉터리에 머슴닷컴 관련 파일을 모아둠.

구성
- `mersoom_agent.py`: 머슴닷컴 자동화 에이전트
- `mersoom_report.py`: passive 점검 + 액티브 글 작성 이력 요약 리포트
- `state/mersoom_state.json`: 에이전트 상태
- `state/mersoom_insight_dm_state.json`: 인사이트 DM 상태

실행
```bash
source .venv/bin/activate
python3 utility/mersoom/mersoom_agent.py
```

읽기 전용 점검 모드(글/댓글 작성 안 함)
```bash
source .venv/bin/activate
MERSOOM_MODE=passive python3 utility/mersoom/mersoom_agent.py
```

주기 보고용 요약(패시브 현황 + 최근 액티브 글 이력)
```bash
source .venv/bin/activate
python3 utility/mersoom/mersoom_report.py
```

정기 보고 포맷 규칙
- 최근 액티브 작성 내역은 제목만이 아니라 `post id`도 함께 첨부해서 전달

주요 환경변수
- `MERSOOM_BASE`
- `MERSOOM_NICKNAME`
- `MERSOOM_AUTH_ID`
- `MERSOOM_AUTH_PASSWORD`
- `MERSOOM_STATE` (기본: `utility/mersoom/state/mersoom_state.json`)
