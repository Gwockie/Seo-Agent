from pathlib import Path
import json
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

def get_credentials(secret_dir: Path, *, reauth: bool = False, account: str | None = None) -> Credentials:
    secret_dir.mkdir(parents=True, exist_ok=True)
    client_file = secret_dir / "client_secret.json"
    token_file = secret_dir / "token.json"

    if not client_file.exists():
        raise FileNotFoundError(
            f"Missing {client_file}. Download a Google OAuth Desktop-app credential "
            "JSON and save it at that path."
        )

    creds = None
    if token_file.exists() and not reauth:
        saved = json.loads(token_file.read_text(encoding="utf-8"))
        if set(saved.get("scopes", [])) != set(SCOPES):
            raise ValueError("Saved token scopes differ from the read-only scope. Remove secrets/token.json locally and authorize again.")
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            raise ValueError("Google authorization expired or was revoked. Remove secrets/token.json locally and run auth again. If the app is in Testing, add the Search Console account as a test user.") from None
        token_file.write_text(creds.to_json(), encoding="utf-8")

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        print("Complete Google login and consent in the browser using the account with Search Console access.", flush=True)
        options = {"login_hint": account} if account else {}
        try:
            creds = flow.run_local_server(port=0, access_type="offline", prompt="select_account consent", timeout_seconds=300, authorization_prompt_message=None, **options)
        except WSGITimeoutError:
            raise ValueError("Google consent did not return to the local callback within five minutes. Run auth again and complete consent in the newly opened browser window. The previous token was preserved.") from None
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds
