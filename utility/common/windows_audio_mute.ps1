# Windows system mute key trigger (used by WSL wrapper)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class KeySend {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
}
"@

# VK_VOLUME_MUTE = 0xAD, KEYEVENTF_KEYUP = 0x2
[KeySend]::keybd_event(0xAD, 0, 0, 0)
Start-Sleep -Milliseconds 80
[KeySend]::keybd_event(0xAD, 0, 2, 0)
