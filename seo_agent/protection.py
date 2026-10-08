"""Read-only Windows ACL/encryption verification. Never changes machine policy."""
import json
import os
from pathlib import Path
import subprocess


class ProtectionError(ValueError):
    """Safe operator-facing prerequisite failure, with no source exception data."""


def existing_ancestor(path: Path) -> Path:
    path = path.resolve()
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def storage_status(path: Path) -> dict:
    path = path.resolve()
    if not path.exists():
        parent = existing_ancestor(path)
        status = storage_status(parent)
        return {**status, "verified": False, "exists": False, "checked_path": str(parent), "parent_reason": status["reason"],
                "reason": "Directory does not exist. The existing parent must pass protection before workspace creation."}
    if os.name != "nt":
        return {"verified": False, "exists": True, "reason": "Live private data requires verified Windows ACLs and EFS/BitLocker storage."}
    # Pass path as an environment value, never interpolate it into PowerShell.
    script = r'''
$ErrorActionPreference = 'Stop'
$p = (Resolve-Path -LiteralPath $env:SEO_CHECK_PATH).Path
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$allowed = @($sid, 'S-1-5-18', 'S-1-5-32-544')
$disk = $false
$diskState = 'unknown'
try {
    $drive = [IO.Path]::GetPathRoot($p).TrimEnd('\')
    $vol = Get-BitLockerVolume -MountPoint $drive -ErrorAction Stop
    $disk = ($vol.ProtectionStatus -eq 'On' -and $vol.VolumeStatus -eq 'FullyEncrypted')
    $diskState = if ($disk) { 'verified' } else { 'not-protected' }
} catch {}
$queue = New-Object 'System.Collections.Generic.Queue[string]'
$queue.Enqueue($p)
$checked = 0; $badAcl = 0; $plain = 0; $reparse = 0
while ($queue.Count -gt 0) {
    if ($checked -ge 10000) { throw 'Storage verification entry limit exceeded' }
    $item = Get-Item -LiteralPath $queue.Dequeue() -Force
    $checked++
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { $reparse++; continue }
    $acl = Get-Acl -LiteralPath $item.FullName
    $bad = @($acl.Access | Where-Object {
        $_.AccessControlType -eq 'Allow' -and
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -notin $allowed
    })
    if ($bad.Count -gt 0) { $badAcl++ }
    $efs = ($item.Attributes -band [IO.FileAttributes]::Encrypted) -ne 0
    if (-not ($efs -or $disk)) { $plain++ }
    if ($item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $item.FullName -Force) { $queue.Enqueue($child.FullName) }
    }
}
@{ acl = ($badAcl -eq 0); encrypted = ($plain -eq 0); checked_entries = $checked;
   broad_acl_entries = $badAcl; unencrypted_entries = $plain; reparse_entries = $reparse;
   bitlocker = $diskState } | ConvertTo-Json -Compress
'''
    try:
        # Windows PowerShell 5 cannot load inherited PowerShell 7 module paths.
        modules = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "Modules")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env={**os.environ, "SEO_CHECK_PATH": str(path), "PSModulePath": modules}, capture_output=True, text=True, timeout=30, check=True)
        status = json.loads(result.stdout)
        if not isinstance(status, dict) or any(type(status.get(k)) is not bool for k in ("acl", "encrypted")) or any(type(status.get(k)) is not int or status[k] < 0 for k in ("checked_entries", "broad_acl_entries", "unencrypted_entries", "reparse_entries")) or not 1 <= status["checked_entries"] <= 10000:
            raise ValueError("Invalid protection response")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"verified": False, "exists": True, "reason": "Windows storage protection could not be verified; live auditing and private backup are disabled."}
    verified = status["acl"] and status["encrypted"] and not any(status[k] for k in ("broad_acl_entries", "unencrypted_entries", "reparse_entries"))
    return {**status, "verified": verified, "exists": True, "reason": "Storage protection verified for this directory and its existing contents." if verified else "Live private data requires operator-only ACLs and verified EFS or fully protected BitLocker for every existing entry; reparse points are rejected. See setup documentation."}


def require_protected(path: Path):
    result = storage_status(path)
    if not result["verified"]:
        raise ProtectionError(result["reason"])
