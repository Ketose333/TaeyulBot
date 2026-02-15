# Git Initial Reset Utility

이니셜커밋 강제정리 표준 절차:
1) 현재 변경사항을 패치로 임시 보관
2) `memory/git-history-archive.md` 갱신
3) orphan 이니셜커밋 생성 + 원격 force push
4) 보관한 최신 변경사항을 후속 커밋으로 push

## 실행

```bash
bash /home/user/.openclaw/workspace/utility/git/initial_reset_with_latest.sh
```

옵션:
- `--no-latest` : 후속 커밋 단계 생략(이니셜만 반영)
