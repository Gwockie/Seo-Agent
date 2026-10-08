"""Trusted configuration. Client facts and locations never live in industry profiles."""
from __future__ import annotations

import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ID_PATTERN = r"^[a-f0-9]{32}$"
PROFILE_VERSION = "1.0"
BASE_RULES = {
    "indexing": {"version": "1.0", "scope": "general", "requires": "priority crawl/inspection rows", "condition": "intended indexed page; exclude intentional exclusions", "settings": {"enabled": True}},
    "canonical": {"version": "1.0", "scope": "general", "requires": "priority page canonical evidence", "condition": "canonical differs from intended URL; exclude intentional exclusions", "settings": {"enabled": True}},
    "broken_link": {"version": "1.0", "scope": "general", "requires": "source link and fetched destination 404/410", "condition": "destination actually crawled", "settings": {"enabled": True}},
    "alignment": {"version": "1.0", "scope": "general", "requires": "query/page rows and intended landing page", "condition": "query matches configured active phrase", "settings": {"enabled": True, "min_impressions": 10}},
    "relevance": {"version": "1.0", "scope": "general", "requires": "200 HTML priority page title/headings and site terms", "condition": "configured terms absent from title/headings", "settings": {"enabled": True}},
    "ctr": {"version": "1.0", "scope": "general", "requires": "query/page rows with sample size", "condition": "position <= 10; diagnostic lead only", "settings": {"enabled": True, "min_impressions": 100, "ctr_threshold": 0.03}},
}
PSYCHOLOGY_RULES = {
    "clinical_review": {"version": "1.0", "scope": "psychology", "requires": "own-site relevance finding on a configured service page", "condition": "content review requires clinician confirmation", "settings": {"enabled": True}},
}
INDUSTRIES = {
    "general": {"version": PROFILE_VERSION, "service_definitions": {}, "confirmations": ["Confirm the business actually offers the configured service and location."]},
    "psychology": {"version": PROFILE_VERSION, "service_definitions": {
        "adhd_assessment": ["ADHD assessment", "ADHD testing", "ADHD evaluation"],
        "psychological_testing": ["psychological testing", "psychological assessment", "psychological evaluation"],
        "therapy": ["therapy", "therapist", "counseling"],
    }, "confirmations": ["Clinician must confirm services, audience, location, licensure, credentials, testing instruments, insurance and any outcome claims before publication."]},
}


def public_url(value: str) -> str:
    if len(value) > 2048 or any(ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Invalid public URL")
    try:
        p = urlsplit(value)
        port = p.port
    except ValueError:
        raise ValueError("Invalid public URL") from None
    if p.scheme not in ("http", "https") or not p.hostname or p.username is not None or p.password is not None:
        raise ValueError("Use a public HTTP(S) URL without credentials")
    if port not in (None, 80 if p.scheme == "http" else 443) or "%" in p.netloc:
        raise ValueError("Only standard HTTP(S) ports are permitted")
    host = p.hostname.lower().rstrip(".")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host) or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Use a public DNS hostname") from None
    else:
        if not addr.is_global or addr.is_multicast or (getattr(addr, "ipv4_mapped", None) and not addr.ipv4_mapped.is_global):
            raise ValueError("Non-public destinations are prohibited")
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def within_site(root: str, url: str) -> bool:
    a, b = urlsplit(public_url(root)), urlsplit(public_url(url))
    # A URL-prefix site cannot read another path subtree on the same host.
    prefix = a.path.rstrip("/")
    return a.netloc == b.netloc and (not prefix or b.path == prefix or b.path.startswith(prefix + "/"))


def validate_property(prop: str, url: str) -> None:
    p = urlsplit(public_url(url))
    if prop.startswith("sc-domain:"):
        domain = prop[10:]
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) or not (p.hostname == domain or p.hostname.endswith("." + domain)):
            raise ValueError("Domain property does not cover this public URL")
    elif not within_site(prop, url) or urlsplit(prop).scheme != p.scheme:
        raise ValueError("Exact URL-prefix property does not cover this public URL")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class Phrase(StrictModel):
    phrase: str = Field(min_length=1, max_length=200)
    group: str = Field(default="service", min_length=1, max_length=80)
    related_terms: list[str] = Field(default_factory=list, max_length=30)
    location: str = Field(default="", max_length=120)
    priority: int = Field(default=3, ge=1, le=5)
    landing_page: str = Field(default="", max_length=2048)
    active: bool = True

    @field_validator("phrase", "group")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Blank phrase/group")
        return v.strip()

    @field_validator("related_terms")
    @classmethod
    def bounded_terms(cls, v):
        if any(not t.strip() or len(t) > 200 for t in v):
            raise ValueError("Invalid related term")
        return v


class RuleOverride(StrictModel):
    enabled: bool | None = None
    min_impressions: int | None = Field(default=None, ge=10, le=10000)
    ctr_threshold: float | None = Field(default=None, ge=0.001, le=0.1)


class SiteConfig(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    url: str
    gsc_property: str
    connection_id: str | None = Field(default=None, pattern=ID_PATTERN)
    industry: Literal["general", "psychology"] = "general"
    profile_version: str = PROFILE_VERSION
    location: str = Field(default="", max_length=120)
    audience: str = Field(default="", max_length=300)
    brand_aliases: list[str] = Field(default_factory=list, max_length=30)
    service_groups: dict[str, list[str]] = Field(default_factory=dict, max_length=30)
    confirmed_facts: dict[str, str] = Field(default_factory=dict, max_length=50)
    exclusions: list[str] = Field(default_factory=list, max_length=100)
    phrases: list[Phrase] = Field(default_factory=list, max_length=500)
    overrides: dict[str, RuleOverride] = Field(default_factory=dict)

    @model_validator(mode="after")
    def relationships(self):
        self.__dict__["url"] = public_url(self.url)
        validate_property(self.gsc_property, self.url)
        if self.profile_version != PROFILE_VERSION:
            raise ValueError("Unsupported industry profile version")
        if any(len(t) > 200 or not t.strip() for t in self.brand_aliases):
            raise ValueError("Invalid brand alias")
        for key, terms in self.service_groups.items():
            if not key.strip() or len(key) > 80 or len(terms) > 30 or any(not t.strip() or len(t) > 200 for t in terms):
                raise ValueError("Invalid service group")
        if any(len(k) > 120 or len(v) > 2000 for k, v in self.confirmed_facts.items()):
            raise ValueError("Fact exceeds size limit")
        seen = set()
        for phrase in self.phrases:
            key = phrase.phrase.casefold()
            if key in seen:
                raise ValueError("Duplicate phrase; import must be unambiguous")
            seen.add(key)
            if phrase.landing_page and not within_site(self.url, phrase.landing_page):
                raise ValueError("Landing page is outside the selected site")
            if phrase.landing_page:
                validate_property(self.gsc_property, phrase.landing_page)
        for url in self.exclusions:
            if not within_site(self.url, url):
                raise ValueError("Exclusion is outside the selected site")
        resolve_rules(self)
        return self


def resolve_rules(config: SiteConfig) -> dict:
    registry = dict(BASE_RULES)
    if config.industry == "psychology":
        registry.update(PSYCHOLOGY_RULES)
    resolved = {}
    for key in config.overrides:
        if key not in registry:
            raise ValueError("Unknown or incompatible rule override")
    for key, rule in registry.items():
        settings = dict(rule["settings"])
        override = config.overrides.get(key)
        if override:
            values = override.model_dump(exclude_none=True)
            if set(values) - set(settings):
                raise ValueError("Setting is not overridable for this rule")
            if key == "clinical_review" and values.get("enabled") is False:
                raise ValueError("Factual confirmation cannot be disabled")
            settings.update(values)
        resolved[key] = {**rule, "settings": settings}
    return {"registry_version": "1.0", "industry": config.industry, "profile_version": config.profile_version,
            "rules": resolved, "guidance": INDUSTRIES[config.industry],
            "immutable_controls": ["read-only GSC", "exact-action production approval", "verified isolated staging with change disclosure", "factual integrity", "site isolation", "public destination validation", "protected credentials"]}


LEGACY_PHRASES = ["ADHD assessment Paoli", "ADHD assessment in Paoli", "ADHD testing Paoli", "ADHD evaluation Paoli", "ADHD assessment near me", "ADHD testing near me", "psychological testing Paoli", "therapy Paoli", "therapist Paoli", "therapy near me"]


def legacy_phrases() -> list[Phrase]:
    return [Phrase(phrase=p, group="adhd_assessment" if "ADHD" in p else "psychological_testing" if "psychological" in p else "therapy", location="near me" if "near me" in p else "Paoli", priority=5 if "ADHD" in p else 3) for p in LEGACY_PHRASES]


def service_terms(config: SiteConfig, group: str) -> list[str]:
    # Industry vocabulary applies only when this site deliberately chooses that group.
    return config.service_groups.get(group, INDUSTRIES[config.industry]["service_definitions"].get(group, []))
