"""Legacy CLI credentials: read old token without replacing it; new auth is OS-backed."""
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from .config import SCOPE
from .credentials import load_connection, validate_credentials, validate_token_info
SCOPES = [SCOPE]

def get_credentials(secret_dir: Path, *, reauth=False, account=None):
    if reauth or account:
        raise ValueError("Use auth --connection ID for explicit secure reconnection")
    pointer = secret_dir / "connection.json"
    if pointer.exists():
        try:
            cid = json.loads(pointer.read_text(encoding="utf-8"))["connection_id"]
        except (ValueError, KeyError):
            raise ValueError("Invalid CLI connection reference") from None
        return load_connection(cid)
    token = secret_dir / "token.json"
    if not token.exists():
        raise ValueError("No selected Google connection. Run auth or explicitly migrate the legacy token.")
    if token.stat().st_size > 16000:
        raise ValueError("Legacy token exceeds size limit")
    saved = json.loads(token.read_text(encoding="utf-8"))
    validate_token_info(saved)
    creds = Credentials.from_authorized_user_info(saved, SCOPES)
    validate_credentials(creds)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            validate_credentials(creds)
        except Exception:
            raise ValueError("Legacy authorization requires secure reconnection; original token preserved") from None
    if not creds.valid:
        raise ValueError("Legacy authorization is invalid; reconnect securely")
    return creds
