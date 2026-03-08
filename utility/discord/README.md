디스코드 전용 보조 유틸용 폴더.
정책: [`policy/media.md`](../../policy/media.md), [`policy/ops.md`](../../policy/ops.md)

포함 스크립트
- Discord bulk delete 실제 구현: `studio/dashboard/actions/discord_bulk_delete_action.py`

## 기본 운영

- 기본 경로는 대시보드(`studio/dashboard/webui.py`)에서 실행한다.
- 대시보드의 `운영 실행 > DM 일괄 삭제`를 우선 사용한다.
- 이 액션은 **대시보드/venv 전용**으로 본다. 시스템 `python3` 단독 실행은 `discord` 모듈 부재로 실패할 수 있다.

## 수동/백업 실행

```bash
# 런타임 시작(수동, venv 전용)
/home/user/.openclaw/workspace/.venv/bin/python \
  studio/dashboard/actions/discord_bulk_delete_action.py run --poll-sec 2

# 작업 큐 등록(수동, venv 전용)
/home/user/.openclaw/workspace/.venv/bin/python \
  studio/dashboard/actions/discord_bulk_delete_action.py enqueue \
  --channel-id 1470802274518433885 \
  --limit 300 --auto-author --skip-pinned

# 권장: 대시보드 운영 실행 카드에서 직접 실행
```

런타임 파일:
- queue: `studio/dashboard/runtime/discord_bulk_delete_queue.jsonl`
- runs: `studio/dashboard/runtime/discord_bulk_delete_runs.jsonl`
