# YouTube Watch Utility

새 유튜브 영상(쇼츠 포함) 알림 크론을 빠르게 등록하기 위한 유틸리티.

## 1) 크론 job JSON 생성

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCmnuDfK6fqL2hIWKjAmXJ-Q \
  --target 753783778157264936
```

출력된 JSON을 그대로 `cron.add`의 `job`으로 넣으면 됨.

## 2) 로컬 레지스트리 저장(선택)

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCxxxx \
  --target 753783778157264936 \
  --interval-min 15 \
  --save
```

저장 파일: `utility/youtube_watch/state/channels.json`

## 3) agentTurn message만 출력

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCxxxx \
  --target 753783778157264936 \
  --message-only
```

## 메모
- 상태 파일은 채널별로 `memory/youtube-watch-<channel_id>.json` 사용
- 첫 실행은 최신 영상 ID만 초기화하고 알림을 보내지 않음
- 이후 새 영상만 중복 없이 알림
