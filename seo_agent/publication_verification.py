"""Compare only explicitly declared effects in exact saved public snapshots."""
import json
from datetime import datetime
from typing import Literal

from bs4 import BeautifulSoup
from pydantic import Field, model_validator
from soupsieve import SelectorSyntaxError, compile as compile_selector

from .config import ID_PATTERN, StrictModel, public_url, within_site
from .page_tracking import extract, text_value
from .tracking import digest, timestamp


TEXT_KINDS = {"heading", "breadcrumb", "navigation_label"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
INERT_TAGS = {"template", "script", "style", "noscript"}


class Effect(StrictModel):
    kind: Literal["heading", "breadcrumb", "navigation_label", "document_title",
                  "canonical", "robots", "googlebot", "x_robots_tag"]
    selector: str | None = Field(default=None, min_length=1, max_length=400)
    before: str = Field(max_length=8000)
    after: str = Field(max_length=8000)

    @model_validator(mode="after")
    def explicit_location(self):
        if (self.kind in TEXT_KINDS) != (self.selector is not None):
            raise ValueError("Provide a selector for each heading, breadcrumb and navigation label")
        if self.selector is not None:
            try:
                compile_selector(self.selector)
            except SelectorSyntaxError:
                raise ValueError("Invalid effect selector") from None
        return self


class Page(StrictModel):
    url: str = Field(max_length=2048)
    before_snapshot_id: str = Field(pattern=ID_PATTERN)
    after_snapshot_id: str = Field(pattern=ID_PATTERN)
    effects: list[Effect] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def distinct_effects(self):
        locations = [effect.selector or effect.kind for effect in self.effects]
        if len(set(locations)) != len(locations):
            raise ValueError("Declare each effect location once per URL")
        return self


class Expectations(StrictModel):
    schema_version: Literal["seo-publication-expectations/1"]
    site_id: str = Field(pattern=ID_PATTERN)
    pages: list[Page] = Field(min_length=1, max_length=20)


def _capture(row, snapshot_id, url):
    reference = {"snapshot_id": snapshot_id}
    if row is None or row["url"] != url:
        return reference, None, "No saved capture for this exact site and URL"
    reference |= {"checked_utc": row["checked"], "status": row["status"],
                  "record_sha256": digest(dict(row))}
    if row["status"] != "complete":
        return reference, None, "Saved capture is unavailable"
    try:
        payload = json.loads(row["payload"])
        if not isinstance(payload, dict):
            raise ValueError
        headers = payload.get("headers", {})
        html = payload.get("html")
        if (payload.get("http_status") != 200 or payload.get("final_url") != url
                or ("synthetic" in payload and type(payload["synthetic"]) is not bool)
                or not isinstance(html, str) or not isinstance(headers, dict)
                or any(not isinstance(value, str) for value in headers.values())
                or payload.get("values") != extract(html, url, headers)):
            raise ValueError
        duplicate_attribute = False

        def flag_duplicate(_attributes, _name, _value):
            nonlocal duplicate_attribute
            duplicate_attribute = True

        soup = BeautifulSoup(html, "html.parser", on_duplicate_attribute=flag_duplicate)
        if duplicate_attribute:
            return reference, None, "Saved HTML contains ambiguous duplicate attributes"
        if (len(soup.find_all("html")) != 1 or len(soup.find_all("head")) != 1
                or len(soup.find_all("body")) != 1 or soup.head.parent is not soup.html
                or soup.body.parent is not soup.html):
            raise ValueError
        checked = datetime.fromisoformat(timestamp(row["checked"]))
    except (ValueError, RecursionError):
        return reference, None, "Saved capture has incomplete or inconsistent source evidence"
    reference["synthetic"] = payload.get("synthetic")
    return reference, (soup, headers, checked), None


def _inert(node):
    return (node.name in INERT_TAGS or node.has_attr("hidden")
            or node.get("aria-hidden", "").casefold() == "true")


def _observe(source, reason, effect):
    if source is None:
        return {"value": None, "reason": reason}
    soup, headers, _ = source
    if effect.selector is not None:
        try:
            nodes = soup.select(effect.selector, limit=2)
        except RecursionError:
            nodes = []
    elif effect.kind == "x_robots_tag":
        values = [value for key, value in headers.items() if key.casefold() == "x-robots-tag"]
        if len(values) == 1:
            return {"value": values[0]}
        return {"value": None, "reason": "Expected one explicitly captured X-Robots-Tag field"}
    elif effect.kind == "document_title":
        nodes = soup.head.find_all("title", recursive=False)
    elif effect.kind == "canonical":
        nodes = soup.find_all("link", rel=lambda rel: bool(rel and rel.casefold() == "canonical"))
    else:
        nodes = soup.find_all("meta", attrs={"name": lambda name: bool(name and name.casefold() == effect.kind)})
    if len(nodes) != 1:
        return {"value": None, "reason": "Expected exactly one element at the declared location"}

    node = nodes[0]
    if effect.selector is not None:
        if (soup.body not in node.parents or (effect.kind == "heading" and node.name not in HEADINGS)
                or _inert(node) or any(_inert(parent) for parent in node.parents)
                or node.find(_inert)):
            return {"value": None, "reason": "Declared element has no unambiguous static body text"}
        return {"value": text_value(node.get_text()), "tag": node.name}
    if node.parent is not soup.head:
        return {"value": None, "reason": "Expected the declared metadata in the document head"}
    if effect.kind == "document_title":
        if not node.find(True):
            return {"value": text_value(node.get_text())}
    elif effect.kind == "canonical":
        href = node.get("href")
        if href and href.strip():
            return {"value": href}
    elif node.has_attr("content") and node["content"].strip():
        return {"value": node["content"]}
    return {"value": None, "reason": "Declared metadata has no usable value"}


def _compare(effect, before, after, pair_reason):
    if pair_reason is None and before["value"] is not None and after["value"] is not None:
        if before.get("tag") != after.get("tag"):
            pair_reason = "The selector resolved to different element types"
        else:
            matched = (before["value"], after["value"]) == (effect.before, effect.after)
            status = "matches_expectation" if matched else "mismatch"
            return {"expectation": effect.model_dump(), "before": before, "after": after, "status": status}
    result = {"expectation": effect.model_dump(), "before": before, "after": after, "status": "unavailable"}
    if pair_reason:
        result["reason"] = pair_reason
    return result


def report(store, declaration):
    """Return a read-only evidence report, with no approval or receipt semantics."""
    expected = Expectations.model_validate(declaration)
    root = store.site(expected.site_id).url
    urls = [page.url for page in expected.pages]
    if len(set(urls)) != len(urls) or any(public_url(url) != url or not within_site(root, url) for url in urls):
        raise ValueError("Declare distinct exact URLs within the selected site")
    ids = sorted({identity for page in expected.pages for identity in (page.before_snapshot_id, page.after_snapshot_id)})
    placeholders = ", ".join("?" for _ in ids)
    with store.db() as db:
        rows = {row["id"]: row for row in db.execute(
            f"SELECT * FROM public_snapshots WHERE site_id=? AND id IN ({placeholders})", (expected.site_id, *ids))}
    pages = []
    for page in expected.pages:
        before_id, after_id = page.before_snapshot_id, page.after_snapshot_id
        before_ref, before, before_reason = _capture(rows.get(before_id), before_id, page.url)
        after_ref, after, after_reason = _capture(rows.get(after_id), after_id, page.url)
        pair_reason = None
        if before and after:
            if before[2] >= after[2]:
                pair_reason = "Before capture must precede after capture"
            elif before_ref["synthetic"] != after_ref["synthetic"]:
                pair_reason = "Capture provenance differs"
        pages.append({"url": page.url, "before_capture": before_ref, "after_capture": after_ref,
                      "effects": [_compare(effect, _observe(before, before_reason, effect),
                                           _observe(after, after_reason, effect), pair_reason)
                                  for effect in page.effects]})
    return {"schema_version": "seo-publication-verification/1", "site_id": expected.site_id,
            "expectations_sha256": digest(expected.model_dump()), "pages": pages}
