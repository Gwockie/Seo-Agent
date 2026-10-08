"""Read-only Windows ACL/encryption verification. Never changes machine policy."""
import json
import os
from pathlib import Path
import subprocess


def storage_status(path: Path) -> dict:
    if os.name != "nt":
        return {"verified": False, "reason": "Live private data requires verified Windows ACLs and EFS/BitLocker storage."}
    # Pass path as an environment value, never interpolate it into PowerShell.
    script = r'''
$ErrorActionPreference = 'Stop'
$p = (Resolve-Path -LiteralPath $env:SEO_CHECK_PATH).Path
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$acl = Get-Acl -LiteralPath $p
$allowed = @($sid, 'S-1-5-18', 'S-1-5-32-544')
$bad = @($acl.Access | Where-Object {
    $_.AccessControlType -eq 'Allow' -and
    $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -notin $allowed
})
$efs = ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::Encrypted) -ne 0
$disk = $false
try {
    $drive = [IO.Path]::GetPathRoot($p).TrimEnd('\')
    $vol = Get-BitLockerVolume -MountPoint $drive -ErrorAction Stop
    $disk = ($vol.ProtectionStatus -eq 'On' -and $vol.VolumeStatus -eq 'FullyEncrypted')
} catch {}
@{ acl = ($bad.Count -eq 0); encrypted = ($efs -or $disk) } | ConvertTo-Json -Compress
'''
    try:
        # Windows PowerShell 5 cannot load inherited PowerShell 7 module paths.
        modules = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "Modules")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env={**os.environ, "SEO_CHECK_PATH": str(path.resolve()), "PSModulePath": modules}, capture_output=True, text=True, timeout=15, check=True)
        status = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"verified": False, "reason": "Windows storage protection could not be verified; live auditing and private backup are disabled."}
    verified = bool(status.get("acl") and status.get("encrypted"))
    return {"verified": verified, "acl": bool(status.get("acl")), "encrypted": bool(status.get("encrypted")), "reason": "Storage protection verified." if verified else "Live private data requires an operator-only ACL and verified EFS or fully protected BitLocker. See setup documentation."}


def require_protected(path: Path):
    result = storage_status(path)
    if not result["verified"]:
        raise ValueError(result["reason"])
