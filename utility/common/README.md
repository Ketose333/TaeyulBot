공용 유틸 헬퍼 코드용 폴더.
정책/운영 기준은 [`utility/README.md`](../README.md)를 우선 참조.

## Windows/WSL 네트워크 헬퍼

### `windows_wsl_portproxy_autoupdate.ps1`
WSL IP가 바뀌어도 Windows portproxy(예: 8767/8787/8791)를 자동으로 갱신하는 스크립트.

관리자 PowerShell에서 1회 실행:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\\Users\\<YOU>\\.openclaw\\workspace\\utility\\common\\windows_wsl_portproxy_autoupdate.ps1" -Ports 8767,8787,8791 -InstallTask
```

- `-InstallTask`를 주면 로그인 시 자동 갱신 스케줄러(`TaeyulBot-WSL-PortProxy-AutoUpdate`)도 같이 등록됨.
- 수동 갱신만 원하면 `-InstallTask` 없이 실행.
