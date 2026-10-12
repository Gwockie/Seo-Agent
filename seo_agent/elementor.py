"""Offline Elementor heading mapping and previews; no CMS access or authority.

This is preparation for a distinct adapter. None of these results may be passed
to the core-block publisher, or used as proof of installation compatibility.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

from bs4 import BeautifulSoup

from .wordpress import CMSFailure

MAX_BYTES = 2 * 1024 * 1024


def _reject():
    raise CMSFailure("Elementor data or heading mapping is unsupported or ambiguous") from None


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            _reject()
        value[key] = item
    return value


def _number(raw):
    value = float(raw)
    if not math.isfinite(value):
        _reject()
    return value


def _plain(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 500
            or any(c in value for c in "<>[]\r\n")
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        _reject()
    return value


def _unlinked(link):
    if link is None:
        return True
    return (isinstance(link, dict)
            and not set(link) - {"url", "is_external", "nofollow", "custom_attributes"}
            and all(value in (None, "", False) for value in link.values()))


def _parse(raw):
    """Strict JSON plus lexical spans: a preview changes only one string token."""
    if not isinstance(raw, str):
        _reject()
    try:
        if len(raw.encode("utf-8")) > MAX_BYTES:
            _reject()
        value = json.loads(raw, object_pairs_hook=_pairs, parse_float=_number,
                           parse_constant=lambda _: _reject())
        decoder, spans, count = json.JSONDecoder(), {}, 0

        def space(pos):
            while pos < len(raw) and raw[pos] in " \t\r\n":
                pos += 1
            return pos

        def visit(pos, path, depth):
            nonlocal count
            count += 1
            if depth > 64 or count > 20000:
                _reject()
            start = pos = space(pos)
            if raw[pos] == "{":
                pos = space(pos + 1)
                while raw[pos] != "}":
                    key, pos = decoder.raw_decode(raw, pos)
                    pos = visit(space(pos) + 1, path + (key,), depth + 1)
                    pos = space(pos)
                    if raw[pos] == "}":
                        break
                    pos = space(pos + 1)
                pos += 1
            elif raw[pos] == "[":
                pos, index = space(pos + 1), 0
                while raw[pos] != "]":
                    pos = space(visit(pos, path + (index,), depth + 1))
                    index += 1
                    if raw[pos] == "]":
                        break
                    pos = space(pos + 1)
                pos += 1
            else:
                _, pos = decoder.raw_decode(raw, pos)
            spans[path] = (start, pos)
            return pos

        visit(0, (), 0)
        if not isinstance(value, list):
            _reject()  # Raw _elementor_data array, not a template export envelope.
        return value, spans
    except (ValueError, IndexError, RecursionError, UnicodeError):
        _reject()  # Never echo input, parser context, or an export's other fields.


@dataclass(frozen=True)
class HeadingMapping:
    """Inert mapping. page_id is supplied CMS evidence, never derived from HTML."""
    page_id: int
    element_id: str
    ancestor_ids: tuple
    path: tuple
    tag: str
    current: str
    source_sha256: str


def map_heading(raw, *, page_id, element_id):
    if (type(page_id) is not int or page_id < 1 or not isinstance(element_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", element_id)):
        _reject()
    data, _ = _parse(raw)
    identities, selected = set(), []

    def walk(elements, path, ancestors):
        if not isinstance(elements, list):
            _reject()
        for index, node in enumerate(elements):
            if not isinstance(node, dict):
                _reject()
            identity, kind = node.get("id"), node.get("elType")
            settings, children = node.get("settings"), node.get("elements")
            if (not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identity)
                    or identity in identities or not isinstance(kind, str)
                    or kind not in {"section", "column", "container", "widget"}
                    or not (isinstance(settings, dict) or settings == []) or not isinstance(children, list)):
                _reject()
            identities.add(identity)
            settings = settings or {}
            widget_type = node.get("widgetType")
            if kind == "widget" and not isinstance(widget_type, str):
                _reject()
            # Any unresolved shared/dynamic dependency keeps this narrow preparation blocked.
            if (kind == "widget" and widget_type in {"global", "template"}
                    or node.get("templateID") or settings.get("template_id")
                    or settings.get("__dynamic__") or settings.get("__globals__")):
                _reject()
            here = path + (index,)
            if identity == element_id:
                if (kind != "widget" or widget_type != "heading" or children
                        or not _unlinked(settings.get("link"))
                        or not isinstance(settings.get("header_size"), str)
                        or settings.get("header_size") not in {"h1", "h2", "h3", "h4", "h5", "h6"}):
                    _reject()
                selected.append(HeadingMapping(page_id, identity, ancestors,
                    here + ("settings", "title"), settings["header_size"],
                    _plain(settings.get("title")), hashlib.sha256(raw.encode("utf-8")).hexdigest()))
            walk(children, here + ("elements",), ancestors + (identity,))

    walk(data, (), ())
    if len(selected) != 1:
        _reject()
    return selected[0]


def preview_heading(raw, mapping, proposed):
    """Return local JSON preview; no writes, network requests, or approval state."""
    if type(mapping) is not HeadingMapping or _plain(proposed) == mapping.current:
        _reject()
    fresh = map_heading(raw, page_id=mapping.page_id, element_id=mapping.element_id)
    if fresh != mapping:
        raise CMSFailure("Elementor document changed since mapping; refresh the review")
    _, spans = _parse(raw)
    start, end = spans[mapping.path]
    replacement = json.dumps(proposed, ensure_ascii=True)
    return raw[:start] + replacement + raw[end:]


def bind_rendered_heading(source, mapping):
    """Cross-check CMS-derived identity against one page-local public heading."""
    if type(mapping) is not HeadingMapping or not isinstance(source, str):
        _reject()
    try:
        if len(source.encode("utf-8")) > MAX_BYTES:
            _reject()
    except UnicodeError:
        _reject()
    soup = BeautifulSoup(source, "html.parser")
    documents = soup.find_all(attrs={"data-elementor-id": str(mapping.page_id)})
    if len(documents) != 1 or documents[0].get("data-elementor-type") != "wp-page":
        _reject()
    document = documents[0]
    # A shared document can be nested beneath (or around) a page document without
    # adding a data-id. Containment and widget ancestry alone cannot prove locality.
    def document_boundary(node):
        return node.has_attr("data-elementor-id") or node.has_attr("data-elementor-type")

    if any(document_boundary(parent) for parent in document.parents):
        _reject()
    # Identity must be unique across the whole response, including shared templates.
    widgets = soup.find_all(attrs={"data-id": mapping.element_id})
    if len(widgets) != 1 or document not in widgets[0].parents:
        _reject()
    widget = widgets[0]
    if document_boundary(widget) or any(document_boundary(child) for child in widget.find_all(True)):
        _reject()
    ancestors = []
    for parent in widget.parents:
        if parent is document:
            break
        if document_boundary(parent):
            _reject()
        if parent.get("data-id"):
            identity = parent["data-id"]
            if len(soup.find_all(attrs={"data-id": identity})) != 1:
                _reject()
            ancestors.append(identity)
    if tuple(reversed(ancestors)) != mapping.ancestor_ids:
        _reject()
    if widget.get("data-widget_type") != "heading.default":
        _reject()
    headings = widget.find_all(re.compile("^h[1-6]$"))
    if (len(headings) != 1 or headings[0].name != mapping.tag or headings[0].find(True)
            or headings[0].find_parent("a") or headings[0].get_text() != mapping.current):
        _reject()
    # This validates the selected heading only; host/plugin effects remain uncertified.
    return {"page_id": mapping.page_id, "element_id": mapping.element_id,
            "tag": mapping.tag, "text": mapping.current, "publishing_compatible": False}
