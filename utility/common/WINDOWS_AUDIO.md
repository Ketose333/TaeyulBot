# Windows Audio Utility (via WSL)

사용법:

```bash
# 토글(기본)
bash /home/user/.openclaw/workspace/utility/common/windows_audio_mute.sh

# 강제 음소거
bash /home/user/.openclaw/workspace/utility/common/windows_audio_mute.sh mute

# 다시 켜기(해제)
bash /home/user/.openclaw/workspace/utility/common/windows_audio_mute.sh unmute
```

구성:
- `utility/common/windows_audio_mute.ps1` : Windows API로 음소거 키 전송
- `utility/common/windows_audio_mute.sh` : WSL 래퍼 + 상태기반 모드(toggle/mute/unmute)
- `unmute`는 볼륨 레벨을 건드리지 않고 mute 해제만 수행(볼륨 값 유지 목적)
