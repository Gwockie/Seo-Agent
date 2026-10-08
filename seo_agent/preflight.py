"""Read-only setup diagnostics. Never creates a workspace, refreshes or shows tokens."""
import json
from pathlib import Path
from google.oauth2.credentials import Credentials

from .config import SCOPE
from .credentials import WindowsVault, MAX_BLOB_BYTES, credential_payload
from .protection import storage_status
from .storage import private_location, credential_location


def setup_status(workspace: Path, secrets: Path, legacy_root: Path) -> dict:
    workspace = private_location(workspace)
    secrets = credential_location(secrets)
    storage = {"workspace": storage_status(workspace), "secrets": storage_status(secrets)}
    for name in ("data", "reports"):
        storage["legacy_" + name] = storage_status(legacy_root / name)
    try:
        WindowsVault()  # Backend selection only; no credential read/write/probe.
        backend = "Windows WinVaultKeyring selected; access requires a later non-sensitive probe"
    except ValueError:
        backend = "unavailable; no fallback permitted"
    client_ok = False
    try:
        client_file = secrets / "client_secret.json"
        if client_file.stat().st_size <= 16000:
            client = json.loads(client_file.read_text(encoding="utf-8"))
            installed = client.get("installed", {})
            client_ok = installed.get("auth_uri") == "https://accounts.google.com/o/oauth2/auth" and installed.get("token_uri") == "https://oauth2.googleapis.com/token" and all(isinstance(installed.get(k), str) and installed[k] for k in ("client_id", "client_secret"))
    except (OSError, ValueError, AttributeError):
        pass
    token = {"present": (secrets / "token.json").is_file(), "format_and_size_valid": False,
             "payload_limit_utf16_bytes": MAX_BLOB_BYTES, "live_access": "not tested"}
    if token["present"]:
        try:
            path = secrets / "token.json"
            if path.stat().st_size <= 16000:
                raw = path.read_text(encoding="utf-8")
                token["payload_utf16_bytes"] = len(raw.encode("utf-16-le"))
                credential_payload(raw)
                Credentials.from_authorized_user_info(json.loads(raw), [SCOPE])
                token["format_and_size_valid"] = True
        except (OSError, ValueError, TypeError):
            pass
    return {"storage": storage, "credential_backend": backend, "desktop_client_format_valid": client_ok,
            "legacy_token": token, "live_ready": False,
            "next_step": "Verify workspace and credential storage first. Then explicitly seed/select the original site, create a new connection ID, validate Google property access and register protected history. This diagnostic does not authorize or prove live access."}
