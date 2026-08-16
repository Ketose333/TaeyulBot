# TaeyulBot — 진행상황 (STATUS)

마지막 갱신: 2026-08-16

## 인프라

| 항목 | 값 |
| --- | --- |
| 런타임 | Python 3.10, discord.py |
| LLM | Gemini 기본/폴백 + Groq `openai/gpt-oss-120b` |
| LLM 오케스트레이션 | LangChain, owner-only 파일 도구 allowlist |
| 자동 검증 | PR마다 pytest와 값 비출력 시크릿 스캔 |

## 마지막 머지

- PR #12 — 종료된 Groq Llama 3.3 70B를 GPT-OSS 120B로 교체
- 전체 테스트 154건 및 실제 Groq local tool calling 통과

## 다음 작업

- [ ] P1 — 이슈 #11: `.github/workflows/**` CODEOWNERS/ruleset 적용, Action SHA 및 Python 의존성 고정

## 알려진 이슈

| 이슈 | 비고 |
| --- | --- |
| PR이 자동 검증 workflow를 함께 변경할 수 있음 | 이슈 #11에서 코드오너 승인 또는 중앙 required workflow 검토 |
| 일부 Python 의존성이 무버전 | 이슈 #11에서 lock/constraints 도입 검토 |
