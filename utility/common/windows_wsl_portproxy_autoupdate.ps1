param(
    [string]$Ports = "8767,8787,8791",
    [string]$Distro = "",    # optional specific distro name
    [switch]$InstallTask,      # create/update scheduled task
    [string]$TaskName = "TaeyulBot-WSL-PortProxy-AutoUpdate",
    [switch]$VerboseLog
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$ts] $msg"
}

function Get-WSLIp {
    $targetDistro = $Distro
    if (-not $targetDistro -or $targetDistro.Trim().Length -eq 0) {
        try {
            $distros = (& wsl.exe -l -q | Out-String) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
            if ($distros -contains 'Ubuntu') {
                $targetDistro = 'Ubuntu'
            }
        } catch {}
    }

    $linuxCmds = @(
        'hostname -I 2>/dev/null | awk ''{print $1}''',
        'ip -4 -o addr show scope global 2>/dev/null | awk ''{print $4}'' | cut -d/ -f1 | head -n1',
        'ip route get 1 2>/dev/null | awk ''{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}'''
    )

    foreach ($cmd in $linuxCmds) {
        if ($targetDistro -and $targetDistro.Trim().Length -gt 0) {
            $ip = (& wsl.exe -d $targetDistro sh -lc $cmd | Out-String).Trim()
        } else {
            $ip = (& wsl.exe sh -lc $cmd | Out-String).Trim()
        }
        if ($ip -match '^\d+\.\d+\.\d+\.\d+$' -and -not $ip.StartsWith('127.')) {
            return $ip
        }
    }

    throw "WSL IP를 가져오지 못했습니다. (-Distro Ubuntu 로 재시도)"
}

function Get-PortList {
    $items = $Ports -split '[,\s]+' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $out = @()
    foreach ($it in $items) {
        $n = 0
        if ([int]::TryParse($it, [ref]$n) -and $n -ge 1 -and $n -le 65535) {
            $out += $n
        }
    }
    if ($out.Count -eq 0) { throw "유효한 포트가 없습니다. 예: -Ports 8767,8787,8791" }
    return $out | Select-Object -Unique
}

function Ensure-FirewallRule([int]$port) {
    $name = "WSL-PortProxy-$port"
    $exists = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if (-not $exists) {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
        Write-Info "Firewall rule created: $name"
    } elseif ($VerboseLog) {
        Write-Info "Firewall rule exists: $name"
    }
}

function Set-PortProxy([int]$port, [string]$wslIp) {
    # delete existing mapping for listen port (ignore failures)
    & netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$port | Out-Null

    & netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$port connectaddress=$wslIp connectport=$port
    if ($LASTEXITCODE -ne 0) {
        throw "portproxy 설정 실패: ${port} -> ${wslIp}:${port}"
    }

    Write-Info "PortProxy updated: 0.0.0.0:${port} -> ${wslIp}:${port}"
}

function Install-StartupTask {
    $scriptPath = $PSCommandPath
    if (-not $scriptPath) { $scriptPath = $MyInvocation.MyCommand.Path }
    if (-not $scriptPath) { throw "스크립트 경로를 확인할 수 없습니다." }

    $portArgs = (Get-PortList | ForEach-Object { $_.ToString() }) -join ','
    $distroArg = ""
    if ($Distro -and $Distro.Trim().Length -gt 0) {
        $distroArg = " -Distro `"$Distro`""
    }

    $psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Ports $portArgs$distroArg"

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Write-Info "Scheduled task installed/updated: $TaskName"
}

# admin check
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    throw "관리자 PowerShell로 실행해야 합니다."
}

$portList = Get-PortList
$wslIp = Get-WSLIp
Write-Info "Detected WSL IP: $wslIp"
Write-Info "Ports: $($portList -join ',')"

foreach ($p in $portList) {
    Set-PortProxy -port $p -wslIp $wslIp
    Ensure-FirewallRule -port $p
}

if ($InstallTask) {
    Install-StartupTask
}

Write-Info "완료. 현재 portproxy 목록:"
& netsh interface portproxy show all
