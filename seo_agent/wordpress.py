"""Bounded WordPress companion client. No generic REST field writer or redirects."""
import json
import html as html_module
import re
import time
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .credentials import WindowsVault
from .public_fetch import PublicAdapter
from .storage import checked_id

SERVICE = "LocalSEOAudit.WordPress.v1"
PROTOCOL = "local-seo-heading/1"


class CMSFailure(ValueError):
    pass


class CMSVault:
    def __init__(self):
        self.backend = WindowsVault().backend

    def write(self, key, username, password):
        checked_id(key)
        if not username.strip() or not password.strip() or len(username) > 100 or len(password) > 200:
            raise CMSFailure("A dedicated username and application password are required")
        try:
            self.backend.set_password(SERVICE, key, json.dumps([username, password]))
        except Exception:
            raise CMSFailure("Windows CMS credential storage unavailable") from None

    def read(self, key):
        try:
            value = json.loads(self.backend.get_password(SERVICE, checked_id(key)) or "null")
            if not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, str) and v for v in value):
                raise ValueError()
            return tuple(value)
        except Exception:
            raise CMSFailure("Reconnect this destination's dedicated CMS credentials") from None


def destination_url(url, environment):
    p = urlsplit(url)
    local = p.hostname in {"127.0.0.1", "localhost", "::1"}
    if p.username or p.password or p.query or p.fragment or not url.endswith("/"):
        raise CMSFailure("Use an exact canonical WordPress home URL ending in /")
    if environment == "local":
        if not local or p.scheme != "http":
            raise CMSFailure("Local tests require a loopback HTTP destination")
    elif environment not in {"production", "staging"} or p.scheme != "https" or local:
        raise CMSFailure("Hosted destinations require HTTPS")
    return url


class WordPress:
    def __init__(self, destination, vault=None):
        self.destination = destination
        self.base = destination_url(destination["url"], destination["environment"])
        adapter = destination.get("adapter", "core-heading/1")
        if adapter not in {"core-heading/1", "elementor-heading/1"}:
            raise CMSFailure("Unsupported publishing adapter")
        self.route = "local-seo-elementor/v1" if adapter == "elementor-heading/1" else "local-seo/v1"
        self.auth = (vault or CMSVault()).read(destination["credential_id"])
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.clear()
        self.session.headers.update({"User-Agent": "LocalSEOApprovedPublisher/1", "Accept-Encoding": "identity"})
        if destination["environment"] != "local":
            self.session.mount("https://", PublicAdapter(max_retries=0))

    def close(self):
        self.session.close()

    def request(self, method, path, body=None, *, public=False):
        url = self.base + path
        self.session.cookies.clear()
        try:
            started = time.monotonic()
            with self.session.request(method, url, json=body, auth=None if public else self.auth,
                                      timeout=(5, 20), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise CMSFailure("CMS request rejected or unavailable; reconcile any attempted write")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024 or time.monotonic() - started > 25:
                        raise CMSFailure("CMS response exceeded size limit")
                    chunks.append(chunk)
                raw = b"".join(chunks).decode("utf-8")
                if public:
                    if "html" not in response.headers.get("Content-Type", ""):
                        raise CMSFailure("Rendered HTML unavailable")
                    return {"html": raw, "robots": response.headers.get("X-Robots-Tag", "")}
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise CMSFailure("CMS response must be an object")
                return value
        except (requests.RequestException, UnicodeError, ValueError):
            # Never surface response bodies, URLs containing secrets, or auth-bearing exceptions.
            raise CMSFailure("CMS request unavailable; reconcile any attempted write before retrying") from None

    def state(self, object_id):
        if type(object_id) is not int or object_id < 1:
            raise CMSFailure("Explicit positive WordPress page ID required")
        return self.request("GET", f"?rest_route=/{self.route}/pages/{object_id}")

    def operation(self, object_id, request_id):
        checked_id(request_id)
        return self.request("GET", f"?rest_route=/{self.route}/pages/{object_id}/operations/{request_id}")

    def write(self, object_id, body):
        return self.request("POST", f"?rest_route=/{self.route}/pages/{object_id}", body)

    def public(self, url):
        if not url.startswith(self.base):
            raise CMSFailure("Public URL is outside the configured WordPress home")
        return self.request("GET", url[len(self.base):], public=True)


def inspect_state(destination, state, url):
    if destination.get("adapter") == "elementor-heading/1":
        from .elementor_publishing import inspect_state as inspect_elementor
        return inspect_elementor(destination, state, url)
    if not isinstance(state, dict):
        raise CMSFailure("Invalid CMS state")
    if (state.get("protocol") != PROTOCOL or state.get("instance") != destination["instance"]
            or state.get("home") != destination["url"] or state.get("url") != url
            or state.get("environment") != destination["environment"] or state.get("type") != "page"
            or state.get("status") != "publish" or not state.get("supported")):
        raise CMSFailure("Wrong destination, page identity or unsupported CMS/editor configuration")
    if not re.fullmatch(r"[a-f0-9]{64}", state.get("token", "")):
        raise CMSFailure("Missing CMS concurrency token")
    if not isinstance(state.get("content"), str) or not isinstance(state.get("headings"), list) or not state.get("preserved"):
        raise CMSFailure("Incomplete CMS discovery response")
    for heading in state["headings"]:
        if not isinstance(heading, dict) or not isinstance(heading.get("anchor"), str) or not isinstance(heading.get("text"), str) or type(heading.get("block_index")) is not int:
            raise CMSFailure("Invalid CMS block identifiers")


def rendered(source, anchor, expected):
    """Conservative semantic comparison: mask only the explicitly mapped heading.

    Includes adjacent body text/attributes, links, metadata, canonical, robots and
    JSON-LD. Ignore script execution and style whitespace; never certify layout.
    """
    soup = BeautifulSoup(source["html"], "html.parser")
    nodes = soup.find_all(id=anchor)
    if len(nodes) != 1 or nodes[0].name not in {"h1", "h2", "h3", "h4", "h5", "h6"} or nodes[0].find(True):
        raise CMSFailure("Rendered heading is missing, ambiguous or contains rich text")
    if nodes[0].get_text() != expected:
        raise CMSFailure("Rendered heading differs from the approved value")
    nodes[0].string = "__APPROVED_HEADING__"
    for node in soup.find_all("script"):
        if node.get("type") != "application/ld+json":
            node.decompose()
    for node in soup.find_all("style"):
        node.decompose()
    for text in list(soup.find_all(string=True)):
        from bs4 import Comment
        if isinstance(text, Comment):
            text.extract()
    return {"html": re.sub(r">\s+<", "><", str(soup)).strip(), "robots": source.get("robots", "")}


def bind_public_target(html, target, anchor):
    from .page_tracking import clean_content, text_value
    if not target or target.get("text_child") is not None:
        raise CMSFailure("Only a complete frozen heading target can map to a core heading")
    soup = BeautifulSoup(html, "html.parser")
    clean_content(soup)
    node = soup.body
    for step in target["path"]:
        if node is None:
            raise CMSFailure("Frozen public target is missing")
        children = [c for c in node.children if getattr(c, "name", None) or text_value(str(c))]
        matches = [c for c in children if getattr(c, "name", None) == step["tag"]]
        if [c.name if getattr(c, "name", None) else "#text" for c in children] != step["siblings"] or step["index"] >= len(matches):
            raise CMSFailure("Frozen public target structure changed")
        node = matches[step["index"]]
    if node is None or node.get("id") != anchor or node.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        raise CMSFailure("CMS heading does not match the frozen public target")


def masked_content(content, anchor, expected):
    pattern = r'(<h[1-6]\b[^>]*\bid="' + re.escape(anchor) + r'"[^>]*>)([^<>]*)(</h[1-6]>)'
    matches = list(re.finditer(pattern, content))
    if len(matches) != 1 or html_module.unescape(matches[0][2]) != expected:
        raise CMSFailure("Raw CMS heading value is ambiguous or incorrect")
    m = matches[0]
    return content[:m.start(2)] + "__APPROVED_HEADING__" + content[m.end(2):]
