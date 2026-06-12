# 한태율 🔮

Discord 별자리 운세 봇. 오늘의 12별자리 순위·운세·월간 통계 차트를 제공합니다.

---

## 봇 명령어

| 명령어 | 설명 |
|---|---|
| `/별자리순위` | 오늘의 12별자리 운세 순위 (어제 대비 🔺🔻 변동 표시) |
| `/별자리운세 [별자리]` | 특정 별자리 운세 + 행운의 색·숫자·방향 (미입력 시 등록된 별자리 사용) |
| `/내별자리 <별자리>` | 나의 별자리 등록 (통계·프로필·궁합·리더보드에 사용) |
| `/궁합 [상대] [별자리1] [별자리2]` | 두 별자리의 오행 궁합 점수·풀이 |
| `/리더보드` | 이달 평균 순위가 좋은 이용자 랭킹 (서버 멤버 기준, DM은 전체) |
| `/오늘의기운` | 오늘의 천간·오행 기운과 기운 받는/주의할 별자리 안내 |

운세 메시지 내 드랍다운·버튼으로 다른 별자리 전환, 통계 그래프, 프로필(최근 7일 순위 타임라인) 확인 가능.  
User-Installable App — 서버 없이 DM에서도 사용 가능.

---

## 로컬 개발

```bash
git clone https://github.com/<your-username>/taeyulbot.git
cd taeyulbot

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

**Windows PowerShell — SSH 키 권한 설정 (처음 1회)**
```powershell
# <KEY_PATH>를 실제 경로로, <USERNAME>을 Windows 유저명으로 교체
icacls "<KEY_PATH>" /inheritance:r /grant:r "<USERNAME>:R"
```

**접속**
```bash
ssh -i "<KEY_PATH>" ubuntu@<SERVER_IP>
```

> SSH 키 파일은 분실하면 복구 불가. 구글 드라이브 등 안전한 곳에 백업 권장.

---

### C. VM 초기 설정 (서버에서, 최초 1회)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git fonts-nanum

git clone https://github.com/<your-username>/taeyulbot.git taeyulbot
cd taeyulbot
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
WorkingDirectory=/home/ubuntu/taeyulbot
ExecStart=/home/ubuntu/taeyulbot/venv/bin/python main.py
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
cd ~/taeyulbot
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
taeyulbot/
├── main.py
├── app/
│   ├── bot.py                   # 봇 초기화, persistent view 등록
│   ├── commands/horoscope.py    # 슬래시 커맨드 + 버튼/드랍다운
│   ├── services/
│   │   ├── horoscope_service.py # 운세 생성·캐싱
│   │   ├── stats_service.py     # 월간 통계 집계
│   │   └── ranking_service.py  # 일일 순위 생성
│   └── utils/
│       ├── saju_engine.py       # 별자리 데이터·운세 텍스트
│       ├── stats_chart.py       # matplotlib 순위 차트
│       ├── date_utils.py        # KST 날짜 헬퍼, history.json I/O
│       └── user_store.py        # 유저 별자리 등록 (data/users.json)
├── data/
│   ├── history.json             # 일별 운세 히스토리 (30일)
│   └── users.json               # 유저 별자리 등록 정보
├── assets/
│   ├── jalsalge.png             # 1위 반응 이미지
│   └── jalgake.png              # 12위 반응 이미지
├── .env.example
└── requirements.txt
```
