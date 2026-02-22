#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/user/.openclaw/workspace"
cd "$ROOT"

APPLY_LATEST=1
if [[ "${1:-}" == "--no-latest" ]]; then
  APPLY_LATEST=0
fi

PATCH_FILE="/tmp/openclaw_latest_after_initial.patch"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
OLD_HEAD="$(git rev-parse HEAD)"
NOW_KST="$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"

# 1) Save latest local changes (tracked + untracked) as patch
# intent-to-add to include untracked files in patch
while IFS= read -r f; do
  git add -N "$f" || true
done < <(git ls-files --others --exclude-standard)

git diff --binary > "$PATCH_FILE" || true

git restore --worktree --staged .

# 2) refresh history note before reset
cat > memory/git-history-archive.md <<EOF
# Git History Archive

- reset 시점: ${NOW_KST}
- reset 직전 HEAD: ${OLD_HEAD}
- 목적: 이니셜커밋으로 히스토리 정리 후, 최신 변경사항은 후속 커밋으로 누적

## 기억 포인트(최근 주요 변경 20개)
EOF

git log --pretty='- %ad | %h | %s' --date=short -n 20 >> memory/git-history-archive.md

git add memory/git-history-archive.md
if ! git diff --cached --quiet; then
  git commit -m "docs: refresh history memory note before initial reset" >/dev/null
fi

# 3) initial commit first
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
fi

git checkout --orphan temp_initial

git add -A
git commit -m "Initial commit"

git branch -D "$CURRENT_BRANCH"
git branch -m "$CURRENT_BRANCH"

git push -f origin "$CURRENT_BRANCH"

# 4) apply latest changes on top
if [[ $APPLY_LATEST -eq 1 && -s "$PATCH_FILE" ]]; then
  git apply "$PATCH_FILE" || git apply --reject "$PATCH_FILE"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    git commit -m "chore: apply latest updates after initial reset"
    git push --set-upstream origin "$CURRENT_BRANCH" || git push
  fi
fi

echo "done: initial-first workflow completed"
