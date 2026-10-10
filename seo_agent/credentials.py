"""Explicit Windows Credential Manager adapter with no plaintext fallback."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import SCOPE
from .storage import checked_id

SERVICE = "LocalSEOAudit.Google.v1"
MAX_BLOB_BYTES = 2560  # Windows generic credential limit; keyring encodes UTF-16LE.


class ConnectionError(ValueError):
    def __init__(self, category, retryable=False):
        self.category, self.retryable = category, retryable
        super().__init__("Selected Google connection needs attention: " + category + "; reconnect this exact connection if access is revoked. No fallback account.")


def bounded_refresh_request():
    request = Request()
    def bounded(*args, **kwargs):
        kwargs["timeout"] = 20
        return request(*args, **kwargs)
    return bounded


def validate_scopes(values):
    if isinstance(values, str):
        values = values.split()
    if set(values or []) != {SCOPE}:
        raise ValueError("Google scopes must be exactly webmasters.readonly")


def validate_credentials(creds):
    validate_scopes(creds.scopes)
    if creds.granted_scopes is not None:
        validate_scopes(creds.granted_scopes)


def credential_payload(raw: str) -> str:
    if len(raw.encode("utf-16-le")) > MAX_BLOB_BYTES:
        raise ValueError("Token exceeds the Windows credential payload limit. Migration unavailable; a reviewed OS-protected blob adapter is required. Legacy token preserved.")
    try:
        saved = json.loads(raw)
    except ValueError:
        raise ValueError("Invalid credential data") from None
    validate_token_info(saved)
    return raw


def validate_token_info(saved):
    if not isinstance(saved, dict):
        raise ValueError("Invalid credential data")
    validate_scopes(saved.get("scopes"))
    # Google token endpoints/client data may only be loaded from the trusted format.
    if saved.get("token_uri") != "https://oauth2.googleapis.com/token" or saved.get("universe_domain", "googleapis.com") != "googleapis.com":
        raise ValueError("Unexpected Google token endpoint/domain")
    if any(key not in {"token", "refresh_token", "token_uri", "client_id", "client_secret", "scopes", "expiry", "universe_domain", "account", "rapt_token"} for key in saved):
        raise ValueError("Unexpected credential fields")


class WindowsVault:
    def __init__(self):
        from keyring.backends.Windows import WinVaultKeyring
        if os.name != "nt" or type(keyring.get_keyring()) is not WinVaultKeyring:
            raise ValueError("Secure Windows WinVaultKeyring backend unavailable; plaintext fallback is prohibited")
        self.backend = keyring.get_keyring()

    def probe(self):
        name = "probe-" + uuid.uuid4().hex
        try:
            self.backend.set_password(SERVICE, name, "non-sensitive-storage-probe")
            if self.backend.get_password(SERVICE, name) != "non-sensitive-storage-probe":
                raise ValueError("Credential store probe failed")
        except Exception:
            raise ValueError("Windows credential store access/probe unavailable") from None
        finally:
            try:
                self.backend.delete_password(SERVICE, name)
            except Exception:
                pass

    def read(self, connection_id):
        try:
            value = self.backend.get_password(SERVICE, checked_id(connection_id))
        except Exception:
            raise ValueError("Selected Google connection cannot be loaded") from None
        if not value:
            raise ValueError("Selected connection requires reconnection; no fallback account")
        return credential_payload(value)

    def exists(self, connection_id):
        try:
            return self.backend.get_password(SERVICE, checked_id(connection_id)) is not None
        except Exception:
            raise ValueError("Cannot verify unused connection ID; migration rejected") from None

    def write(self, connection_id, raw):
        raw = credential_payload(raw)
        checked_id(connection_id)
        try:
            self.backend.set_password(SERVICE, connection_id, raw)
        except Exception:
            raise ValueError("Windows credential store write failed") from None


def load_connection(connection_id: str, vault=None):
    vault = vault or WindowsVault()
    try:
        raw = vault.read(connection_id)
        credential_payload(raw)
        creds = Credentials.from_authorized_user_info(json.loads(raw), [SCOPE])
        validate_credentials(creds)
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(bounded_refresh_request())
            except Exception as exc:
                from google.auth.exceptions import TransportError
                raise ConnectionError("temporary_google_network" if isinstance(exc, TransportError) else "access_reconnect", isinstance(exc, TransportError)) from None
            validate_credentials(creds)
            payload = credential_payload(creds.to_json())
            vault.write(connection_id, payload)
            if vault.read(connection_id) != payload:
                raise ConnectionError("vault_persistence_failed")
        if not creds.valid:
            raise ValueError("Selected connection requires reconnection")
        original_refresh = creds.refresh
        def persisted_refresh(request):
            try:
                try:
                    original_refresh(request)
                except Exception as exc:
                    from google.auth.exceptions import TransportError
                    raise ConnectionError("temporary_google_network" if isinstance(exc, TransportError) else "access_reconnect", isinstance(exc, TransportError)) from None
                validate_credentials(creds)
                payload = credential_payload(creds.to_json())
                vault.write(connection_id, payload)
                if vault.read(connection_id) != payload:
                    raise ConnectionError("vault_persistence_failed")
            except ConnectionError:
                raise
            except Exception:
                raise ConnectionError("connection_scope_size_or_vault_invalid") from None
        creds.refresh = persisted_refresh
        creds._seo_connection_id = connection_id
        return creds
    except ConnectionError:
        raise
    except Exception:
        raise ConnectionError("connection_scope_size_or_vault_invalid") from None


def authorize_connection(connection_id: str, client_file: Path, *, account=None):
    vault = WindowsVault()
    vault.probe()
    try:
        if client_file.stat().st_size > 16000:
            raise ValueError("Desktop OAuth JSON exceeds import limit")
        client = json.loads(client_file.read_text(encoding="utf-8"))
        if "installed" not in client or client["installed"].get("auth_uri") != "https://accounts.google.com/o/oauth2/auth" or client["installed"].get("token_uri") != "https://oauth2.googleapis.com/token":
            raise ValueError("Expected Google Desktop OAuth JSON")
        flow = InstalledAppFlow.from_client_config(client, [SCOPE])
        creds = flow.run_local_server(host="127.0.0.1", port=0, access_type="offline", prompt="select_account consent", timeout_seconds=300, authorization_prompt_message=None, **({"login_hint": account} if account else {}))
        validate_credentials(creds)
        raw = credential_payload(creds.to_json())
        # Consent failure/scope/size validation cannot replace a working account.
        vault.write(connection_id, raw)
    except Exception:
        raise ValueError("Google consent failed or credential size/scopes were rejected. Existing connections were preserved.") from None


def migrate_legacy(token_file: Path, connection_id: str, site_config, *, vault=None, service_factory=None):
    """Copy only to a NEW connection after exact property access and round-trip checks."""
    from .gsc import service_for_credentials, validate_access
    vault = vault or WindowsVault()
    vault.probe()
    # Even invalid/oversized existing credentials must never be replaced by migration.
    if vault.exists(connection_id):
        raise ValueError("Migration requires a new unused connection ID")
    if token_file.stat().st_size > 16000:
        raise ValueError("Legacy credential file exceeds import limit")
    raw = credential_payload(token_file.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(json.loads(raw), [SCOPE])
    validate_credentials(creds)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(bounded_refresh_request())
        except Exception:
            raise ValueError("Legacy Google connection cannot be refreshed") from None
        validate_credentials(creds)
        raw = credential_payload(creds.to_json())
    svc = (service_factory or service_for_credentials)(creds)
    validate_access(svc, site_config.gsc_property, site_config.url)
    vault.write(connection_id, raw)
    if vault.read(connection_id) != raw:
        raise ValueError("Credential migration round-trip failed; legacy file preserved")
    # Do not unlink, rewrite or even refresh the original token file.
