#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-toggle}" # toggle | mute | unmute
STATE_FILE="/home/user/.openclaw/workspace/utility/common/.windows_audio_state"

mkdir -p "$(dirname "$STATE_FILE")"
[[ -f "$STATE_FILE" ]] || echo "unknown" > "$STATE_FILE"

run_toggle() {
  /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -NoProfile \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w /home/user/.openclaw/workspace/utility/common/windows_audio_mute.ps1)" >/dev/null 2>&1
}

current_state="unknown"
if [[ -f "$STATE_FILE" ]]; then
  current_state="$(cat "$STATE_FILE" 2>/dev/null || echo unknown)"
fi

case "$MODE" in
  toggle)
    run_toggle
    if [[ "$current_state" == "muted" ]]; then
      echo "unmuted" > "$STATE_FILE"
    else
      echo "muted" > "$STATE_FILE"
    fi
    ;;
  mute)
    if [[ "$current_state" != "muted" ]]; then
      run_toggle
      echo "muted" > "$STATE_FILE"
    fi
    ;;
  unmute)
    # 볼륨 레벨(예: 40) 유지 목적: 볼륨 업/다운 키 없이 mute 토글만 사용
    if [[ "$current_state" == "muted" ]]; then
      run_toggle
      echo "unmuted" > "$STATE_FILE"
    fi
    ;;
  *)
    echo "Usage: $0 [toggle|mute|unmute]" >&2
    exit 2
    ;;
esac
