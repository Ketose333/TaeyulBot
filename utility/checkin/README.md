# Ops Check-in Utility

운영 점검(자동 체크리스트 + 사용자 2문항) DM 크론 job JSON 생성기.

## 사용

```bash
python3 utility/checkin/register_ops_checkin.py \
  --target 753783778157264936
```

기본 스케줄:
- 매일 12:00 (Asia/Seoul, TikTok Lite 시간대 동시 실행)

원하면 cron 식 변경:

```bash
python3 utility/checkin/register_ops_checkin.py \
  --target 753783778157264936 \
  --cron "0 21 * * 1,4"
```

출력 JSON을 `cron.add`의 `job`으로 넣으면 됨.
