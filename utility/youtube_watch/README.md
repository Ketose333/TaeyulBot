# YouTube Watch Utility

이 디렉터리는 YouTube watcher 등록/점검용 **실행 가이드 전용**이다.
정책: [`policy/routing.md`](../../policy/routing.md)

## 1) 크론 job JSON 생성

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCmnuDfK6fqL2hIWKjAmXJ-Q \
  --target 753783778157264936
```

출력된 JSON을 그대로 `cron.add`의 `job`으로 사용한다.

## 2) 로컬 레지스트리 저장(선택)

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCxxxx \
  --target 753783778157264936 \
  --interval-min 15 \
  --save
```

저장 파일: `utility/youtube_watch/state/channels.json`

## 3) OAuth 토큰 점검(선택)

```bash
python3 utility/youtube_watch/oauth_access_token.py
```

필요 env:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

## 4) agentTurn message만 출력

```bash
python3 utility/youtube_watch/register_youtube_watch.py \
  --channel-id UCxxxx \
  --target 753783778157264936 \
  --message-only
```

## 5) 통합 watch 스크립트

```bash
python3 utility/youtube_watch/watch.py --task idntt-community
```

- 커뮤니티 감시 같은 확장 기능은 `watch.py`에 통합한다.
- 레거시 진입점은 제거했고, `watch.py`만 사용한다.

## 메모
- 상태 파일은 채널별로 `memory/youtube-watch-<channel_id>.json` 사용
- 첫 실행은 최신 영상 ID만 초기화하고 알림을 보내지 않음
- 이후 새 영상만 중복 없이 알림
