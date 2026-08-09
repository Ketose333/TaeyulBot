<a id="readme-top"></a>

# 한태율

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-5865F2?style=flat-square&logo=discord&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=flat-square&logo=groq&logoColor=white)

Discord AI 컴패니언 봇. 멘션/자유대화로 나누는 일상 대화, 롤플레이 모드, 별자리 운세, 이모지·하트 생성 기능을 제공합니다.

---

## 목차

1. [프로젝트 소개](#프로젝트-소개)
2. [기술 스택](#기술-스택)
3. [봇 기능](#봇-기능)
4. [로컬 개발](#로컬-개발)
5. [서버 배포 (Oracle Cloud Free Tier 기준)](#서버-배포-oracle-cloud-free-tier-기준)
6. [코드 업데이트](#코드-업데이트)
7. [운영 명령어 모음](#운영-명령어-모음)
8. [환경변수 (.env)](#환경변수-env)
9. [Privileged Intent 설정 (필수)](#privileged-intent-설정-필수)
10. [프로젝트 구조](#프로젝트-구조)
11. [로드맵](#로드맵)
12. [라이선스](#라이선스)
13. [연락처](#연락처)

---

## 프로젝트 소개

한태율은 Discord 안에서 일상 대화와 롤플레이, 별자리 운세를 이용할 수 있도록 만든 개인 봇 프로젝트입니다. 채널·DM별 설정과 대화 상태를 분리하며, 공개 초대 링크는 운영 정책상 제공하지 않습니다.

## 기술 스택

- **Runtime**: Python, discord.py
- **AI**: Gemini, Groq
- **Chart**: matplotlib
- **Operations**: Oracle Cloud VM, systemd

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 봇 기능

### 대화 (AI Chat)

멘션하거나 DM을 보내면 Gemini/Groq-Llama 기반으로 대화합니다. 슬래시 커맨드 없이 자연어로 동작하며, 대화 중 필요하면 봇이 스스로 음성 메시지(TTS)를 보내거나("우울한데 노래 추천해줘"처럼) 실제 발매곡을 추천하기도 합니다.

| 명령어 | 설명 |
|---|---|
| `/자유대화` | 이 채널에서 멘션 없이도 모든 메시지에 응답하도록 설정 |
| `/대화초기화` | 현재 채널/DM의 AI 대화 기억 초기화 |
| `/생각수준 [수준]` | 답변의 창의성(논리적/일반적/창의적) 설정 |
| `/모델선정 [모델]` | 1차로 사용할 AI 모델(Gemini/Groq-Llama) 선택 |

### 롤플레이

| 명령어 | 설명 |
|---|---|
| `/롤플레이 시작` | 이 채널/DM에서 RP 모드 시작 (서버 채널이면 전용 스레드 생성) |
| `/롤플레이 끝` | RP 모드 종료 |
| `/롤플레이 이름 [호칭]` | RP 중 나를 부를 호칭 설정 (비우면 해제) |
| `/롤플레이 사용자명` | 현재 설정된 내 호칭 확인 |

### 운세

| 명령어 | 설명 |
|---|---|
| `/운세순위` | 오늘의 12별자리 운세 순위 (어제 대비 🔺🔻 변동 표시) |
| `/운세 [별자리]` | 특정 별자리 운세 + 행운의 색·숫자·방향 (미입력 시 등록된 별자리 사용) |
| `/운세통계 [별자리]` | 이달 별자리 순위 통계 + 추이 그래프 (미입력 시 등록된 별자리 사용) |
| `/별자리 [별자리] [생일]` | 별자리 선택 또는 생일 입력으로 자동 등록 (예: `6월 12일`) |
| `/궁합 [상대] [별자리1] [별자리2]` | 두 별자리의 오행 궁합 점수·풀이 |
| `/리더보드` | 이달 평균 순위가 좋은 이용자 랭킹 (서버 멤버 기준, DM은 전체) |
| `/오늘의기운` | 오늘의 천간·오행 기운과 기운 받는/주의할 별자리 안내 |

운세 메시지 내 드랍다운·버튼으로 다른 별자리 전환, 통계 그래프, 프로필(최근 7일 순위 타임라인) 확인 가능.
미등록 상대에게 궁합을 요청하면 상대가 별자리 선택 또는 생일 입력 후 같은 메시지에서 결과를 확인할 수 있습니다.

### 미디어 생성

이미지/음성은 대화 중 자연어로도(LLM function-calling 도구), 슬래시 커맨드로도 명시적으로 트리거할 수 있습니다.

| 명령어 | 설명 |
|---|---|
| `/이미지생성 [프롬프트]` | 한태율 정체성을 유지한 이미지 생성 (현재 Gemini 무료 티어 쿼터 소진으로 비활성화, `app.config.ENABLE_IMAGE_GENERATION`) |
| `/음성생성 [텍스트]` | 텍스트를 한태율 목소리 음성 파일로 생성 |

### 유틸

| 명령어 | 설명 |
|---|---|
| `/이모지생성 [텍스트]` | 한글 텍스트를 디스코드 커스텀 이모지 스타일 PNG로 렌더링 |
| `/하트생성 [색상]` | 지정한 hex 색상의 하트 이모지 PNG 렌더링 |
| `/음악추천 [상황] [한국곡만]` | 기분/상황에 맞는 실제 발매곡 추천 (Spotify/YouTube Music/Apple Music 링크, 오디오 재생 없음) |

User-Installable App — 서버 없이 DM에서도 모든 기능 사용 가능.

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

---

## 로컬 개발

```bash
git clone https://github.com/Ketose333/TaeyulBot.git
cd TaeyulBot

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env 열어서 DISCORD_TOKEN 입력
```

```bash
python main.py   # 봇 실행
pytest           # 테스트
```

**한국어 차트 폰트** (Ubuntu 서버에서 처음 실행 시 필요):
```bash
sudo apt install -y fonts-nanum
rm -f ~/.cache/matplotlib/fontlist-*.json
```

---

## 서버 배포 (Oracle Cloud Free Tier 기준)

### A. 서버 만들기 (최초 1회)

> 이미 VM이 있으면 B로 건너뛰기

**1. VCN 생성**

OCI 콘솔 → `Networking → Virtual Cloud Networks → Start VCN Wizard`  
기본값으로 생성. (인스턴스 생성 화면에서 인라인으로 만들면 Public IP 할당이 안 됨 — 반드시 여기서 먼저 생성)

**2. 인터넷 게이트웨이 확인**

`VCN 상세 → Route Tables → Default Route Table` 에  
`0.0.0.0/0 → Internet Gateway` 규칙이 없으면 추가.  
이게 없으면 SSH가 타임아웃됨.

**3. 인스턴스 생성**

`Compute → Instances → Create Instance`

- Shape: `VM.Standard.E2.1.Micro` (Always Free)
  - A1.Flex (ARM)는 용량 부족으로 생성 안 될 수 있으므로 x86 권장
- Image: Ubuntu 22.04
- VCN: 위에서 만든 VCN 선택, Public Subnet
- SSH Key: **Generate a key pair** → 반드시 `.key` 파일 다운로드해 보관

**4. 공개 IP 확인**

인스턴스 상세 페이지 → `Primary VNIC → Public IP`

---

### B. SSH 접속

SSH 키 파일(`.key`)이 있는 PC에서 실행.
서버 IP는 고정값 **`132.145.108.135`** (어느 PC에서 접속하든 동일). 키 파일 경로(`<KEY_PATH>`)만 PC에 맞게 바꾸면 됩니다.

**Windows PowerShell — SSH 키 권한 설정 (처음 1회)**
```powershell
# <KEY_PATH>를 실제 경로로, <USERNAME>을 Windows 유저명으로 교체
icacls "<KEY_PATH>" /inheritance:r /grant:r "<USERNAME>:R"
```

**접속**
```bash
ssh -i "<KEY_PATH>" ubuntu@132.145.108.135
```

> SSH 키 파일은 분실하면 복구 불가. 구글 드라이브 등 안전한 곳에 백업 권장.

---

### C. VM 초기 설정 (서버에서, 최초 1회)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git fonts-nanum

git clone https://github.com/Ketose333/TaeyulBot.git
cd TaeyulBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env     # DISCORD_TOKEN 입력 → Ctrl+X → Y → Enter
```

**systemd 서비스 등록 (24/7 자동 실행 + 크래시 자동 복구)**

```bash
sudo nano /etc/systemd/system/taeyulbot.service
```

아래 내용 붙여넣기:

```ini
[Unit]
Description=한태율 Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/TaeyulBot
ExecStart=/home/ubuntu/TaeyulBot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable taeyulbot   # 서버 재부팅 시 자동 시작
sudo systemctl start taeyulbot
sudo systemctl status taeyulbot   # active (running) 확인
```

---

## 코드 업데이트

로컬에서 수정 → push → 서버에서:

```bash
cd ~/TaeyulBot
git pull
source venv/bin/activate
pip install -r requirements.txt   # requirements.txt 변경 시만
sudo systemctl restart taeyulbot
sudo systemctl status taeyulbot
```

---

## 운영 명령어 모음

```bash
# 봇 상태 확인
sudo systemctl status taeyulbot

# 봇 재시작 / 중지 / 시작
sudo systemctl restart taeyulbot
sudo systemctl stop taeyulbot
sudo systemctl start taeyulbot

# 실시간 로그
sudo journalctl -u taeyulbot -f

# 최근 로그 50줄
sudo journalctl -u taeyulbot -n 50
```

---

## 환경변수 (.env)

| 변수 | 필수 | 설명 |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Discord Developer Portal에서 발급 |
| `GUILD_ID` | ❌ | 개발용 서버 ID — 설정 시 슬래시 커맨드 즉시 반영 (미설정 시 글로벌 동기화, 최대 1시간 소요) |
| `GEMINI_API_KEY` | ✅ | AI 대화·운세 통계 차트 외 대부분 기능이 의존. 미설정 시 대화/RP/TTS 불가 |
| `GROQ_API_KEY` | ❌ | `/모델선정`에서 Groq-Llama 선택 시 사용 |
| `OWNER_DISCORD_ID` | ❌ | 설정한 Discord 사용자 ID의 대화에만 `app/persona/USER.md`(개인정보 포함)를 시스템 프롬프트에 추가 주입 |

---

## Privileged Intent 설정 (필수)

`/리더보드`가 서버 멤버를 식별하려면 **Server Members Intent**가 필요합니다.

Developer Portal → 해당 앱 → **Bot** → **Privileged Gateway Intents** →
**Server Members Intent** 토글 ON → 저장.

> 켜지 않으면 봇 기동 시 `PrivilegedIntentsRequired` 오류로 실행되지 않습니다.
> (봇이 100개 미만 서버에 있으면 별도 인증 없이 사용 가능)

---

## 프로젝트 구조

```
TaeyulBot/
├── main.py
├── app/
│   ├── bot.py                        # 봇 초기화, on_message 라우팅, persistent view 등록
│   ├── config.py                     # 환경변수 로딩
│   ├── commands/
│   │   ├── horoscope.py              # 운세 슬래시 커맨드
│   │   ├── horoscope_embeds.py       # 운세 임베드 빌더
│   │   ├── horoscope_ui.py           # 운세 버튼/드랍다운 View
│   │   ├── roleplay.py               # /롤플레이 슬래시 커맨드
│   │   ├── bot_settings.py           # /자유대화, /대화초기화, /생각수준, /모델선정
│   │   ├── emoji.py                  # /이모지생성, /하트생성
│   │   ├── media.py                  # /이미지생성, /음성생성
│   │   └── music.py                  # /음악추천
│   ├── services/
│   │   ├── chat_orchestrator.py      # on_message → LLM 응답 라우팅 서비스 계층
│   │   ├── llm_service.py            # Gemini/Groq 호출, 시스템 프롬프트 조립, function-calling 도구 등록
│   │   ├── horoscope_service.py      # 운세 생성·캐싱
│   │   ├── stats_service.py          # 월간 통계 집계
│   │   └── ranking_service.py        # 일일 순위 생성
│   ├── utils/
│   │   ├── saju_engine.py            # 별자리 데이터·운세 텍스트
│   │   ├── stats_chart.py            # matplotlib 순위 차트
│   │   ├── date_utils.py             # KST 날짜 헬퍼, history.json I/O
│   │   ├── user_store.py             # 유저 별자리 등록 (data/users.json)
│   │   ├── channel_settings.py       # 채널별 자유대화/모델/생각수준 설정 (data/*.json)
│   │   ├── rp_store.py / rp_prompt.py# 롤플레이 상태·프롬프트 조립
│   │   ├── gemini_client.py          # Gemini API 클라이언트
│   │   ├── gemini_tts.py             # 음성 메시지 생성(TTS)
│   │   ├── gemini_image.py           # 이미지 생성 (현재 비활성화)
│   │   ├── media_tools.py            # LLM function-calling 도구(이미지/음성 생성)
│   │   ├── emoji_engine.py / heart_engine.py  # 이모지·하트 PNG 렌더링
│   │   └── json_store.py             # 원자적 JSON 읽기/쓰기 공용 유틸
│   ├── persona/                      # SOUL/IDENTITY/EMOTION/USER.md — 시스템 프롬프트 조립 원본
│   └── assets/                       # 아바타, 폰트, 이모지 스타일, 이미지 프리셋
├── data/                             # 런타임 상태 (users.json, history.json, rp_rooms.json, chat_history.json 등)
├── assets/
│   ├── jalsalge.png                  # 1위 반응 이미지
│   └── jalgage.png                   # 12위 반응 이미지
├── tests/
├── .env.example
└── requirements.txt
```

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 로드맵

- [x] Discord 대화와 채널별 설정
- [x] 별자리 등록·일일 운세·월간 통계
- [x] 사용자 설치 앱과 DM 사용 지원
- [ ] 운영 데이터의 영속 저장소 전환 검토

## 라이선스

별도 오픈소스 라이선스는 지정되어 있지 않습니다.

## 연락처

- GitHub: [Ketose333](https://github.com/Ketose333)
- 문의: 이 저장소의 GitHub Issues

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>
