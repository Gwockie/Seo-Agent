"""Reviewable mutations limited to one installation's identifiable Windows task."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .weekly_worker import validate_installation

MARKER = "LocalSEOAudit weekly read-only dispatcher v1"
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def task_name(install):
    digest = hashlib.sha256(str(Path(install["workspace"]).resolve()).casefold().encode()).hexdigest()[:16]
    return "LocalSEOAudit-Weekly-" + digest


def task_xml(install, path):
    ET.register_namespace("", NS)
    def element(parent, name, text=None):
        child = ET.SubElement(parent, "{" + NS + "}" + name)
        child.text = text
        return child
    root = ET.Element("{" + NS + "}Task", version="1.3")
    registration = element(root, "RegistrationInfo")
    element(registration, "Description", MARKER)
    triggers = element(root, "Triggers")
    timer = element(triggers, "TimeTrigger")
    element(timer, "Enabled", "true")
    element(timer, "StartBoundary", "2026-01-01T00:00:00Z")
    repeat = element(timer, "Repetition")
    element(repeat, "Interval", "PT15M")
    element(repeat, "StopAtDurationEnd", "false")
    logon = element(triggers, "LogonTrigger")
    element(logon, "Enabled", "true")
    element(logon, "UserId", install["principal"])
    principals = element(root, "Principals")
    principal = element(principals, "Principal"); principal.set("id", "Operator")
    element(principal, "UserId", install["principal"])
    element(principal, "LogonType", "InteractiveToken")
    element(principal, "RunLevel", "LeastPrivilege")
    settings = element(root, "Settings")
    for key, value in {"MultipleInstancesPolicy": "IgnoreNew", "DisallowStartIfOnBatteries": "true",
                       "StopIfGoingOnBatteries": "true", "StartWhenAvailable": "true", "Enabled": "true",
                       "WakeToRun": "false", "ExecutionTimeLimit": "PT35M"}.items():
        element(settings, key, value)
    restart = element(settings, "RestartOnFailure")
    element(restart, "Interval", "PT15M"); element(restart, "Count", "2")
    actions = element(root, "Actions"); actions.set("Context", "Operator")
    action = element(actions, "Exec")
    element(action, "Command", install["pythonw"])
    element(action, "Arguments", subprocess.list2cmdline(["-m", "seo_agent", "weekly-worker", "--installation", str(Path(path).resolve())]))
    element(action, "WorkingDirectory", install["root"])
    return ET.tostring(root, encoding="unicode")


SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$p = [Console]::In.ReadToEnd() | ConvertFrom-Json
$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')
$task = $null
try { $task = $folder.GetTask($p.name) } catch {
    $exception = $_.Exception
    while ($null -ne $exception.InnerException) { $exception = $exception.InnerException }
    if ($exception.HResult -ne -2147024894) { throw }
}
if ($null -ne $task) {
    [xml]$old = $task.Xml
    $manager = New-Object System.Xml.XmlNamespaceManager($old.NameTable)
    $manager.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
    if ($old.SelectSingleNode('/t:Task/t:RegistrationInfo/t:Description', $manager).InnerText -ne $p.marker -or
        $old.SelectSingleNode('/t:Task/t:Principals/t:Principal/t:UserId', $manager).InnerText -ne $p.principal -or
        $old.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Command', $manager).InnerText -ne $p.executable -or
        $old.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Arguments', $manager).InnerText -ne $p.arguments -or
        $old.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:WorkingDirectory', $manager).InnerText -ne $p.root) {
        throw 'Task ownership mismatch'
    }
}
if ($p.action -eq 'status') {
    if ($null -eq $task) { @{registered=$false} | ConvertTo-Json -Compress }
    else { @{registered=$true; enabled=$task.Enabled; state=$task.State; last_result=$task.LastTaskResult;
             next_run=$task.NextRunTime.ToString('o'); xml=$task.Xml} | ConvertTo-Json -Compress }
} else {
    # Atomic comparison immediately before mutation, against the reviewed task.
    $oldXml = if ($null -eq $task) { '' } else { $task.Xml }
    if ($oldXml -cne $p.current_xml) { throw 'Task changed since review' }
    if ($p.action -eq 'register') { $null = $folder.RegisterTask($p.name, $p.xml, 6, $p.principal, $null, 3, $null) }
    elseif ($p.action -eq 'disable' -and $null -ne $task) { $task.Enabled = $false }
    elseif ($p.action -eq 'remove' -and $null -ne $task) { $folder.DeleteTask($p.name, 0) }
    else { throw 'Unsupported task action' }
    @{action=$p.action; applied=$true} | ConvertTo-Json -Compress
}
'''


def invoke(packet):
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
                            input=json.dumps(packet), capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ValueError("Task Scheduler unavailable, changed since review or task ownership rejected")
    return json.loads(result.stdout)


def preview(path, action="register"):
    if action not in {"register", "disable", "remove"}:
        raise ValueError("Unsupported task action")
    install = validate_installation(path, check_executable=False)
    packet = {"name": task_name(install), "marker": MARKER, "principal": install["principal"], "action": "status",
              "executable": install["pythonw"], "root": install["root"],
              "arguments": subprocess.list2cmdline(["-m", "seo_agent", "weekly-worker", "--installation", str(Path(path).resolve())])}
    current = invoke(dict(packet))
    packet.update(action=action, xml=task_xml(install, path), current_xml=current.get("xml", ""))
    digest = hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest()
    return {"packet": packet, "reviewed_sha256": digest, "current": current,
            "executable": install["pythonw"], "working_directory": install["root"],
            "principal": install["principal"], "trigger": "Every 15 minutes and operator logon; site weekly times evaluated in saved IANA timezone",
            "limits": "900 seconds/site; 1800 seconds/dispatcher; Task Scheduler 35 minutes; two task restarts at 15 minutes",
            "power": "AC power; no wake or machine power-policy changes", "logon": "InteractiveToken: selected user must remain signed in; locked desktop supported",
            "rollback": "Disable/remove this exact task; prior XML below permits reviewed restoration"}


def apply(path, action, reviewed_sha256):
    reviewed = preview(path, action)
    if reviewed["reviewed_sha256"] != reviewed_sha256:
        raise ValueError("Review changed; generate a fresh exact task preview")
    # Credential-free rollback XML stays only in protected local storage.
    folder = Path(path).parent
    rollback = folder / ("weekly-task-rollback-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
    rollback.write_text(json.dumps(reviewed, indent=2), encoding="utf-8")
    return invoke(reviewed["packet"])
