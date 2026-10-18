"""Bounded, inert administrator evidence format. No options, users or submissions."""
import json
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from .config import StrictModel

MAX_BYTES = 2 * 1024 * 1024
ISOLATION = ("database", "files_uploads", "editor_settings", "deployment", "installation_identity",
             "access_identity", "no_sync", "no_jobs_webhooks", "no_customer_messages", "restricted_access", "noindex")
HOST_EFFECTS = ("cache", "mirrors", "rendering", "save_lifecycle", "experiments")

# Inert forms observed in Elementor page exports. Only empty-settings built-ins
# are accepted here; this does not evaluate tags or permit mapping dynamic titles.
_EMPTY_DYNAMIC_TAG = re.compile(
    r'\[elementor-tag id="[a-f0-9]{7}" name="(?:post-title|post-url)" '
    r'settings="%7[Bb]%7[Dd]"\]'
)


def reject():
    raise ValueError("Discovery evidence rejected: check the documented bounded schema, scope and non-secret fields") from None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def parse(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                reject()
            result[k] = v
        return result
    try:
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_BYTES:
            reject()
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: reject())
    except Exception:
        reject()


def safe_data(value, depth=0, *, _dynamic_bindings=False):
    """Reject credential-bearing keys/URLs, embedded JSON and common secret formats.

    Free prose must still be sanitized by its administrator. Never accept arbitrary
    WordPress options, SQL dumps, user records or form submissions as this format.
    """
    if depth > 35:
        reject()
    if isinstance(value, dict):
        for k, v in value.items():
            if re.search(r"password|passwd|secret|token|authorization|cookie|api.?key|private.?key|submission", k, re.I):
                reject()
            if _dynamic_bindings and isinstance(v, str) and _EMPTY_DYNAMIC_TAG.fullmatch(v):
                # The exact grammar contains no configurable payload. Still apply
                # the recursion limit; the original string is preserved as evidence.
                safe_data("", depth + 1)
            else:
                safe_data(v, depth + 1, _dynamic_bindings=(k == "__dynamic__" and isinstance(v, dict)))
    elif isinstance(value, list):
        if len(value) > 2000:
            reject()
        for v in value:
            safe_data(v, depth + 1)
    elif isinstance(value, str):
        if (len(value) > 500000 or any(0xD800 <= ord(c) <= 0xDFFF for c in value)
                or re.search(r"-----BEGIN .*PRIVATE KEY|(?:Bearer|Basic)\s+[A-Za-z0-9+/=._-]{12,}|https?://[^\s/]+@|[?&](?:key|token|secret|password|signature|_wpnonce)=|(?:password|secret|access_token|api[_-]?key)[\s\"']*[:=]", value, re.I)):
            reject()
        if value.lstrip().startswith(("{", "[")):
            safe_data(parse(value), depth + 1)
    elif value is not None and type(value) not in (int, bool, float):
        reject()


def timestamp(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt > datetime.now(timezone.utc):
            reject()
        return dt.astimezone(timezone.utc)
    except Exception:
        reject()


class Connection(StrictModel):
    label: str = Field(min_length=1, max_length=100)
    provider: str = Field(default="Unknown", min_length=1, max_length=100)
    method: Literal["public", "wordpress_rest", "administrator_export"]
    url: str = Field(max_length=2048)
    environment: Literal["production", "staging", "local"]
    installation_id: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9._:-]*$")


class Software(StrictModel):
    kind: Literal["core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"]
    name: str = Field(min_length=1, max_length=150)
    version: str = Field(default="", max_length=80)
    active: bool | None = None
    sha256: str = Field(default="", pattern=r"^([a-f0-9]{64})?$")


class Metadata(StrictModel):
    row_id: int = Field(gt=0)
    key: Literal["_elementor_data", "_elementor_page_settings", "_elementor_edit_mode", "_elementor_version", "_wp_page_template"]
    value: str = Field(max_length=500000)


class Page(StrictModel):
    id: int = Field(gt=0)
    url: str = Field(max_length=2048)
    type: Literal["page", "elementor_library", "wp_template", "wp_template_part"] = "page"
    status: Literal["publish"] = "publish"
    template: str = Field(default="", max_length=200)
    raw_content: str | None = Field(default=None, max_length=500000)
    raw_excerpt: str | None = Field(default=None, max_length=20000)
    metadata: list[Metadata] = Field(default_factory=list, max_length=50)
    shared_ids: list[int] = Field(default_factory=list, max_length=100)


class HostFact(StrictModel):
    area: Literal["cache", "mirrors", "rendering", "save_lifecycle", "experiments", "database", "files_uploads",
                  "editor_settings", "deployment", "installation_identity", "access_identity", "no_sync",
                  "no_jobs_webhooks", "no_customer_messages", "restricted_access", "noindex"]
    result: Literal["unknown", "isolated", "not_isolated", "observed"] = "unknown"
    # Concrete resource identifiers are evidence references, never access keys.
    production_resource: str = Field(default="", max_length=300)
    environment_resource: str = Field(default="", max_length=300)
    observation: str = Field(min_length=1, max_length=1500)
    source_reference: str = Field(min_length=1, max_length=300)


class AdministratorExport(StrictModel):
    schema_version: Literal[1]
    site_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    site_url: str
    profile_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    cms_url: str
    environment: Literal["production", "staging", "local"]
    installation_id: str = Field(min_length=1, max_length=100)
    collected_utc: str
    source_reference: str = Field(min_length=5, max_length=300)
    software: list[Software] = Field(default_factory=list, max_length=300)
    # Explicit completeness includes empty MU/drop-in inventories; absence is unknown.
    complete_inventory: list[Literal["core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"]] = Field(default_factory=list, max_length=8)
    pages: list[Page] = Field(default_factory=list, max_length=20)
    host: list[HostFact] = Field(default_factory=list, max_length=20)
