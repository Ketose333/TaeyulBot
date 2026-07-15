# CLAUDE.md — TaeyulBot 프로젝트 컨벤션

전역 규칙(`~/.claude/CLAUDE.md`의 커뮤니케이션/커밋/시크릿 스캔 등)을 그대로 따르되, 이 파일은 TaeyulBot 저장소에만 적용되는 구체값과 패턴을 정의한다. 전역과 충돌하면 이 파일이 우선한다.

## 프로젝트 개요

discord.py 기반 AI 컴패니언 봇. 대화(Gemini/Groq-Llama)·롤플레이·별자리 운세·이미지/음성/음악 생성을 제공한다. Oracle Cloud Free Tier **1GB VM**에서 systemd로 상시 구동 — 무거운 의존성(torch/numpy/sklearn 등 ML 프레임워크)은 절대 추가하지 않는다.

### 설계 배경 (과거 PRD 문서에서 통합 후 삭제, 2026-07-15)

옛 OpenClaw 연동 방식은 모든 디스코드 메시지를 강제로 LLM 컨텍스트에 넘겨 AI가 엉뚱하게 참견하는 문제가 있었다. 그래서 discord.py 봇 본체에 라우팅 필터를 직접 둬서, 아래 조건 중 하나를 만족할 때만 AI가 응답한다(`app/services/chat_orchestrator.py`의 `evaluate_message_routing`이 단일 소스):
1. DM(무조건 통과)
2. 봇 멘션
3. 채널명이 `AI-`로 시작하거나 `llm-타임`
4. `/자유대화`로 활성화된 채널
5. 활성 RP(롤플레이) 채널

일반 슬래시 커맨드(`/운세` 등)와 AI 대화는 완전히 독립된 경로다 — 슬래시 커맨드는 discord.py의 인터랙션 시스템이 애초에 `on_message`를 거치지 않으므로 별도 게이트가 필요 없다.

지속 목표(수치는 참고용, 엄격한 SLA 아님): 1GB VM에서 CPU/RAM 여유를 유지하는 선에서 응답 지연을 짧게 유지하고, Gemini 무료 한도 소진 시 Groq로 자동 폴백해 서비스 중단 없이 24/7 무료로 운영한다. 파인튜닝·RAG·디스코드 외 플랫폼 확장은 스코프 밖으로 유지한다.

## 계층 구조

```
app/commands/   슬래시 커맨드 Cog (discord.py 전용, 비즈니스 로직 없음)
app/services/   오케스트레이션 (LLM 호출, 라우팅 판정, 세션 관리)
app/utils/      순수 로직 (discord import 금지, 동기 함수 위주)
app/persona/    시스템 프롬프트 원문(SOUL/IDENTITY/EMOTION/USER/MEMORY.md)
app/assets/     아바타·폰트·이모지 스타일·이미지 프리셋 (정적 리소스)
data/           런타임 상태 JSON (gitignore 대상, 아래 참고)
tests/          pytest, 소스 파일당 test_{module}.py 1:1 대응
```

단방향 의존만 허용: `commands → services → utils`. utils가 commands/services를 참조하지 않는다.

## 슬래시 커맨드 (Cog 패턴)

`app/commands/{feature}.py`에 `class {Feature}Cog(commands.Cog)` + `async def setup(bot)` 세트로 작성하고, `app/bot.py`의 `setup_hook`에 `await self.load_extension("app.commands.{feature}")`로 등록한다(`emoji.py`, `media.py`, `music.py` 참고).

모든 커맨드에 아래 두 데코레이터를 붙인다(User-Installable App — DM에서도 동작해야 함):
```python
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
```

시간이 걸리는 커맨드(외부 API 호출 등)는 `await interaction.response.defer(thinking=True)` 후 `interaction.followup.send(...)`로 응답한다.

**에러 응답은 항상 `app.utils.discord_reply.send_interaction_error(interaction, message)`를 통해서만 보낸다** — `response`/`followup` 중 어느 쪽을 써야 하는지(`interaction.response.is_done()` 분기)를 대신 처리해주고, `ephemeral=True`(요청자에게만 표시)를 강제한다. 실패는 `❌` 접두사 메시지로 짧게 안내하고 `log.exception`/`log.warning`으로 스택을 남기되, 사용자에게 원본 예외 텍스트를 그대로 노출하지 않는다(긴 API 에러 페이로드는 `media_tools.py`의 `_short_error`로 잘라서 넘긴다). `interaction.response.send_message(...)`/`interaction.followup.send(...)`를 에러 전송에 직접 쓰지 않는다.

## LLM function-calling 도구 (자연어 트리거)

이미지/음성/음악 추천처럼 대화 중 자연어로도 트리거되길 원하는 기능은 `app/utils/{feature}_tools.py`에 `make_{feature}_tools(...) -> list`를 만들고 `langchain_core.tools.@tool` 데코레이터로 감싼다(`media_tools.py`, `music_tools.py` 참고). `app/services/llm_service.py`의 `_invoke_with_tools`에서 `tools += make_{feature}_tools(...)`로 합류시킨다.

**슬래시 커맨드와 LLM 도구는 서로 다른 진입점이지만 같은 순수 로직(`app/utils/{feature}.py`)을 호출**해야 한다 — 로직을 두 번 구현하지 않는다. 도구 반환값은 파일 첨부면 `MediaSink`에 쌓고(현재 응답에서 종류당 1회 제한), 텍스트 데이터(예: 음악 추천 결과)면 문자열을 그대로 반환해 LLM이 자기 말투로 재구성하게 한다.

## 설정값 / 환경변수

- 환경변수는 전부 `app/config.py`에서 `os.getenv`로 로드하고, 다른 모듈은 `from app.config import ...`로만 읽는다(직접 `os.getenv` 산발 호출 금지).
- 기능 on/off 플래그(`ENABLE_IMAGE_GENERATION` 등)도 `config.py`에 둔다 — 슬래시 커맨드와 LLM 도구 양쪽이 같은 플래그를 참조해야 하므로 서비스 파일 안에 로컬 상수로 가두지 않는다.
- 모델명/기본 프롬프트 파라미터(이미지 모델, TTS 보이스, 음악 무드 태그 등)는 `app/utils/generation_defaults.py`에 상수로 모은다.

## 데이터 저장 (`data/*.json`)

`app/utils/json_store.py`의 `read_json`/`atomic_write_json`(임시파일 쓰기 + `os.replace` 원자적 교체)을 통해서만 읽고 쓴다. 새 저장소를 추가하면:
1. `app/utils/{feature}_store.py` 또는 기존 store 파일에 경로 상수 추가 (`os.path.join(os.path.dirname(__file__), "..", "..", "data", "{name}.json")`)
2. **`.gitignore`에 `data/{name}.json` 추가를 잊지 않는다** — 런타임 상태(사용자 등록 정보, 대화 기억, 채널 설정 등)는 절대 커밋하지 않는다. 이번 정리에서 `free_channels.json`/`rp_rooms.json`이 누락돼 있던 걸 발견해 추가했다.

## 테스트

- `tests/test_{module}.py`가 `app/{경로}/{module}.py`와 1:1 대응. 새 모듈을 추가하면 테스트 파일도 같은 커밋에 추가한다.
- 순수 함수는 직접 단위 테스트. 외부 HTTP 호출은 `monkeypatch.setattr("app.utils.{module}.requests.post", ...)`처럼 모듈 경로로 몽키패치(`test_music_recommend.py` 참고).
- 비동기 함수는 `@pytest.mark.asyncio` 명시(auto mode 아님).
- 커밋 전 `pytest` 전체 통과 확인(현재 18개 파일, 177개 테스트).

## README 갱신 규칙

기능을 추가/변경하면 같은 커밋에서 `README.md`를 갱신한다:
- "봇 기능" 섹션의 해당 카테고리 표에 명령어 추가
- "프로젝트 구조" 섹션에 새 파일 추가
- LLM 도구로만 존재하고 슬래시 커맨드가 없는(또는 그 반대인) 기능이면 그 사실을 명시(오해 방지)

## 배포

로컬 커밋/푸시 → 서버 반영:
```
ssh -i "C:\Users\user\.ssh\ssh-key-2026-06-12.key" ubuntu@132.145.108.135
cd ~/TaeyulBot && git pull && source venv/bin/activate
pip install -r requirements.txt   # requirements.txt 변경 시만
sudo systemctl restart taeyulbot && sudo systemctl status taeyulbot
```
슬래시 커맨드는 글로벌 동기화라 전파까지 최대 1시간 걸릴 수 있다(개발 중 즉시 반영하려면 `.env`의 `GUILD_ID` 사용).

## 공개 저장소 주의 (`Ketose333/TaeyulBot`은 public)

- 실제 인물 외모/신원을 묘사하는 프롬프트나 프리셋(예: `app/assets/image_presets/*.json`)처럼 공개돼도 괜찮은지 애매한 자산은 **push 전에 반드시 사용자에게 확인**한다.
- 시크릿 스캔은 전역 규칙 그대로: `git diff --cached | grep -iE "(password|passwd|secret|token|api_key|apikey|access_key|private_key|sk-|ghp_|gho_|glpat-|AKIA|AIza)['\"]?\s*[:=]\s*['\"][^'\"]{8,}"`.
