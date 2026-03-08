# Git Initial Reset Utility

운영 기준: [`AGENTS.md`](../../AGENTS.md)

이니셜 커밋 강제 정리 표준 절차:
1) 현재 변경사항을 패치로 임시 보관
2) [`memory/git-history-archive.md`](../../memory/git-history-archive.md) 갱신
3) orphan 이니셜 커밋 생성 + 원격 강제 푸시
4) 보관한 최신 변경사항을 후속 커밋으로 push

## 대시보드 동작 기준(현재)

- 대시보드(`studio/dashboard/webui.py`)의 `이니셜 커밋으로 밀기`는 **외부 action 스크립트 없이 webui 내부에서 직접 실행**한다.
- 현재 이니셜 리셋은 대시보드 액션 기준으로만 운영한다.

## Gitignore 위생 런타임

```bash
# 런타임 시작(상시)
python3 utility/taeyul/taeyul_cli.py gitignore-hygiene-runtime --poll-sec 10

# 작업 큐 등록(.gitignore에 맞춰 tracked ignored 파일 추적해제)
python3 utility/taeyul/taeyul_cli.py gitignore-hygiene-enqueue --reason "periodic hygiene"
```

파일:
- queue: `memory/runtime/gitignore_hygiene_queue.jsonl`
- runs: `memory/runtime/gitignore_hygiene_runs.jsonl`

## .gitignore 작업 표준(필수)

앞으로 파일 무시 관련 작업은 아래를 한 번에 수행:
1) `.gitignore` 규칙 갱신
2) 이미 추적 중인 대상은 `git rm --cached ...`로 **추적 해제**
3) 커밋/푸시해서 원격에서도 비노출 상태 반영

예시:
```bash
git rm --cached MEMORY.md USER.md memory/*.md memory/channels/*.md
git add .gitignore
git commit -m "chore(gitignore): update ignore rules and untrack sensitive files"
git push
```
