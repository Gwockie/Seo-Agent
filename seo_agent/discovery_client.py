"""Fixed GET-only WordPress readers; no editor, write endpoint or companion assumption."""
import hashlib
import html as html_module
import json
import re
import time
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .credentials import WindowsVault, MAX_BLOB_BYTES
from .storage import checked_id
from .wordpress import destination_url
from .public_fetch import PublicAdapter
from .discovery_models import MAX_BYTES, Page, Software, parse, safe_data

SERVICE = "LocalSEOAudit.CMSDiscovery.v1"


class DiscoveryVault:
    def __init__(self):
        self.backend = WindowsVault().backend  # Exact backend validation, no fallback.

    def write(self, key, username, password):
        checked_id(key)
        try:
            if (not isinstance(username, str) or not isinstance(password, str) or not username.strip()
                    or not password.strip() or ":" in username or len(username) > 100 or len(password) > 200
                    or any(ord(c) < 32 for c in username + password)):
                raise ValueError()
            raw = json.dumps([username, password])
            if len(raw.encode("utf-16-le")) > MAX_BLOB_BYTES:
                raise ValueError()
            self.backend.set_password(SERVICE, key, raw)
            if self.backend.get_password(SERVICE, key) != raw:
                raise ValueError()
        except Exception:
            raise ValueError("Discovery credential storage failed; check Windows vault and application credentials") from None

    def read(self, key):
        try:
            value = json.loads(self.backend.get_password(SERVICE, checked_id(key)) or "null")
            if (not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, str) and v for v in value)
                    or len(value[0]) > 100 or len(value[1]) > 200):
                raise ValueError()
            return tuple(value)
        except Exception:
            raise ValueError("Reconnect this discovery connection in the app") from None


def page_url(base, value):
    p, home = urlsplit(value), urlsplit(base)
    if (p.scheme != home.scheme or p.netloc != home.netloc or not p.path.startswith(home.path)
            or p.username or p.password or p.query or p.fragment or "\\" in value
            or "%" in p.path or any(s in {".", "..", "wp-admin", "wp-json"} or s.lower().endswith(".php") for s in p.path.split("/"))):
        raise ValueError("Page URL is outside the exact configured CMS destination or unsupported")
    return value


def public_page(value, base, expected_id=None):
    try:
        page = Page(id=value["id"], url=page_url(base, value["link"]), status=value["status"],
                    type=value["type"], template=value.get("template", ""))
        if page.type != "page" or (expected_id is not None and page.id != expected_id):
            raise ValueError()
        return page.model_dump()
    except Exception:
        raise ValueError("Published REST page identity is missing or differs from the selected page") from None


class DiscoveryReader:
    def __init__(self, connection, vault=None):
        self.connection = connection
        self.base = destination_url(connection["url"], connection["environment"])
        self.auth = None
        self.vault = vault
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.clear()
        self.session.headers.update({"User-Agent": "LocalSEOReadOnlyDiscovery/1", "Accept-Encoding": "identity", "Connection": "close"})
        if connection["environment"] != "local":
            self.session.mount("https://", PublicAdapter(max_retries=0))
        self.started, self.requests = time.monotonic(), 0

    def close(self):
        self.auth = None
        self.session.close()

    def _get(self, path, *, authenticated=False, html=False):
        """Internal routes only; authenticated URLs cannot be supplied by evidence."""
        allowed = (path in {"?rest_route=/wp/v2/plugins&_fields=plugin,status,version", "?rest_route=/wp/v2/themes&_fields=stylesheet,status,version"}
                   or re.fullmatch(r"\?rest_route=/wp/v2/pages/[1-9][0-9]*&context=edit&_fields=id,link,status,type,template,content,excerpt", path))
        if authenticated and (not allowed or not self.auth):
            raise ValueError("Authenticated discovery route unavailable")
        if not authenticated and path.startswith("?") and not (
                path == "?rest_route=/wp/v2/pages&per_page=20&status=publish&_fields=id,link,status,type,template"
                or re.fullmatch(r"\?rest_route=/wp/v2/pages/[1-9][0-9]*&_fields=id,link,status,type,template", path)):
            raise ValueError("Public discovery route unavailable")
        url = self.base + path
        if not path.startswith("?rest_route="):
            page_url(self.base, url)
        self.requests += 1
        try:
            if self.requests > 48 or time.monotonic() - self.started > 90:
                raise ValueError()
            self.session.cookies.clear()
            start = time.monotonic()
            with self.session.get(url, auth=self.auth if authenticated else None, timeout=(5, 15),
                                  allow_redirects=False, stream=True, verify=True) as response:
                if response.status_code != 200 or int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
                    raise ValueError()
                chunks, size = [], 0
                for chunk in response.iter_content(16384):
                    size += len(chunk)
                    if size > MAX_BYTES or time.monotonic() - start > 20 or time.monotonic() - self.started > 90:
                        raise ValueError()
                    chunks.append(chunk)
                raw = b"".join(chunks).decode("utf-8")
                if html:
                    if "html" not in response.headers.get("Content-Type", ""):
                        raise ValueError()
                    return raw
                return parse(raw)
        except Exception:
            raise ValueError("Read-only CMS request unavailable or rejected; no automatic retry. Check destination, access and response limits") from None

    def public(self, page_ids):
        pages, captures, clues, missing = [], [], [], []
        home = self._get("", html=True)
        soup = BeautifulSoup(home, "html.parser")
        for node in soup.select('meta[name="generator"]'):
            value = node.get("content", "")[:150]
            if value:
                clues.append({"kind": "generator", "value": value})
        for node in soup.find_all(["script", "link"]):
            asset = node.get("src", node.get("href", ""))
            match = re.search(r"/wp-content/(plugins|themes)/([a-zA-Z0-9_.-]{1,100})/", asset)
            if match:
                clues.append({"kind": match[1], "value": match[2]})
        if not page_ids:
            data = self._get("?rest_route=/wp/v2/pages&per_page=20&status=publish&_fields=id,link,status,type,template")
            if not isinstance(data, list) or len(data) > 20:
                raise ValueError("Bounded public page inventory unavailable")
            pages = [public_page(v, self.base) for v in data]
            missing.append("Page inventory is a bounded first page (20 maximum), not a full-site inventory")
        else:
            for pid in page_ids:
                data = self._get(f"?rest_route=/wp/v2/pages/{pid}&_fields=id,link,status,type,template")
                pages.append(public_page(data, self.base, pid))
        # Only explicitly selected pages get rendered captures; no automatic whole-site crawl.
        for page in pages if page_ids else []:
            raw = self._get(page["url"][len(self.base):], html=True)
            soup = BeautifulSoup(raw, "html.parser")
            # Retain all node/identity boundaries (including duplicates) for the
            # strict mapper, but discard forms, script bodies and arbitrary attrs.
            # Removing wrapper nodes could hide a nested shared-document boundary.
            for node in soup.find_all(True):
                node.attrs = {k: v for k, v in node.attrs.items() if k in {
                    "data-elementor-id", "data-elementor-type", "data-id", "data-widget_type"}}
                if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", v) for v in node.attrs.values()):
                    raise ValueError("Rendered CMS identity attributes are unsupported")
            for node in list(soup.find_all(string=True)):
                if not node.find_parent(re.compile(r"^h[1-6]$")):
                    node.extract()
            sanitized = str(soup)
            safe_data(sanitized)
            captures.append({"page_id": page["id"], "url": page["url"], "html": sanitized,
                             "response_sha256": hashlib.sha256(raw.encode()).hexdigest()})
        result = {"pages": pages, "captures": captures, "clues": [dict(x) for x in {tuple(v.items()) for v in clues}][:100], "missing": missing}
        safe_data(result)
        return result

    def authenticated(self, page_ids):
        self.auth = (self.vault or DiscoveryVault()).read(self.connection["credential_id"])
        pages, software, complete, missing = [], [], [], []
        for pid in page_ids:
            data = self._get(f"?rest_route=/wp/v2/pages/{pid}&context=edit&_fields=id,link,status,type,template,content,excerpt", authenticated=True)
            page = public_page(data, self.base, pid)
            page.update(raw_content=data.get("content", {}).get("raw"), raw_excerpt=data.get("excerpt", {}).get("raw"))
            pages.append(Page.model_validate(page).model_dump())
        for kind, route, key in (("plugin", "plugins", "plugin"), ("theme", "themes", "stylesheet")):
            try:
                data = self._get(f"?rest_route=/wp/v2/{route}&_fields={key},status,version", authenticated=True)
                if not isinstance(data, list) or len(data) > 100:
                    raise ValueError()
                software.extend(Software(kind=kind, name=v[key], version=v.get("version", ""),
                                         active=True if v.get("status") in ("active", "network-active") else
                                         False if v.get("status") == "inactive" else None).model_dump() for v in data)
                # Core endpoints may paginate/filter; do not claim exhaustive inventory.
            except Exception:
                missing.append(kind + " inventory unavailable with current permissions; use protected administrator export")
        result = {"pages": pages, "software": software, "complete_inventory": complete,
                  "missing": missing + ["Private metadata row identities, full inventory, installation and host effects require administrator evidence"]}
        password = self.auth[1]
        encodings = {password, json.dumps(password, ensure_ascii=True)[1:-1], json.dumps(password, ensure_ascii=False)[1:-1]}
        def echoed(value):
            if isinstance(value, str):
                return any(secret in value or secret in html_module.unescape(value) for secret in encodings)
            if isinstance(value, dict):
                return any(echoed(k) or echoed(v) for k, v in value.items())
            if isinstance(value, list):
                return any(echoed(v) for v in value)
            return False
        if echoed(result):
            raise ValueError("CMS response echoed access data; evidence was not saved")
        safe_data(result)
        return result
