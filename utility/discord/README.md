디스코드 전용 보조 유틸용 폴더.
정책: [`policy/media.md`](../../policy/media.md), [`policy/ops.md`](../../policy/ops.md)

포함 스크립트
- Discord bulk delete 실제 구현: `studio/dashboard/actions/discord_bulk_delete.py`

## 런타임 사용

```bash
# 런타임 시작(상시)
python3 utility/taeyul/taeyul_cli.py bulk-delete-runtime --poll-sec 2

# 작업 큐 등록
python3 utility/taeyul/taeyul_cli.py bulk-delete-enqueue \
  --channel-id 1470802274518433885 \
  --limit 300
```

런타임 파일:
- queue: `studio/dashboard/runtime/discord_bulk_delete_queue.jsonl`
- runs: `studio/dashboard/runtime/discord_bulk_delete_runs.jsonl`
