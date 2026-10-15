"""Separate, pinned Elementor heading protocol. No authority is created here."""
from dataclasses import asdict, replace
import hashlib
import json
import re

from bs4 import BeautifulSoup

from .elementor import map_heading, preview_heading, bind_rendered_heading, _parse, _plain
from .wordpress import CMSFailure, rendered, bind_public_target

ADAPTER = "elementor-heading/1"
PROTOCOL = "local-seo-elementor/1"
FIELD = "_elementor_data:heading.title"
CONTRACT = "elementor-3.31.3-canvas-heading/1"
SCOPE = (
    "Lock posts/options/metadata inventory briefly. Replace one JSON string token in the exact "
    "_elementor_data metadata row, and its corresponding heading text in the existing post_content mirror; "
    "update post_modified and post_modified_gmt. Commit the before/after raw data, mirror and request "
    "to the server journal atomically. Evict only this page's request-local posts/post_meta cache entries. "
    "Preserve all other rows, JSON bytes, page settings, explicit excerpt, CSS files and generated assets. "
    "No editor, autosave, draft, save hooks, revision, option, kit, global template, CSS regeneration or "
    "global cache flush. Google-font fetching, telemetry, element caching, persistent object/page/CDN caches "
    "and unsupported plugins are blocked; CSS uses the pinned internal rendering mode. "
    "Authentication may update application-password last-used/IP records and host access logs. "
    "Each page commits separately; stop after uncertainty or failed verification."
)


def plain(value):
    _plain(value)
    # Elementor renders wp_kses_post(title), not escaped literal text. Entity-looking
    # values cannot round-trip to the approved visible value on this contract.
    if re.search(r"&(?:#|[A-Za-z])", value):
        raise CMSFailure("Entity-encoded Elementor titles require a different contract")
    return value


def inspect_state(destination, state, url):
    if (not isinstance(state, dict) or state.get("protocol") != PROTOCOL
            or state.get("contract") != CONTRACT or state.get("instance") != destination["instance"]
            or state.get("home") != destination["url"] or state.get("url") != url
            or state.get("environment") != destination["environment"] or state.get("type") != "page"
            or state.get("status") != "publish" or state.get("supported") is not True
            or type(state.get("id")) is not int or type(state.get("metadata_row_id")) is not int
            or state["metadata_row_id"] < 1 or state.get("template") != "elementor_canvas"
            or not isinstance(state.get("content"), str) or not isinstance(state.get("elementor_data"), str)
            or not isinstance(state.get("excerpt"), str) or not state["excerpt"].strip()
            or not isinstance(state.get("headings"), list)):
        raise CMSFailure("Wrong Elementor destination, metadata identity or unsupported effect contract")
    for key in ("token", "preserved", "contract_hash"):
        if not re.fullmatch(r"[a-f0-9]{64}", state.get(key, "")):
            raise CMSFailure("Incomplete Elementor conflict/effect evidence")
    manifest = contract_manifest()
    expected = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if state["contract_hash"] != expected:
        raise CMSFailure("Server adapter certificate differs from the locally validated package")
    if state.get("inventory", {}).get("adapter_hash") != adapter_hash():
        raise CMSFailure("Server writer files differ from the reviewed local adapter package")


def contract_manifest():
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parent.parent / "wordpress/local-seo-publisher/elementor-contract.json").read_text())


def adapter_hash():
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "wordpress/local-seo-publisher"
    return hashlib.sha256((base / "elementor-publisher.php").read_bytes() + (base / "local-seo-publisher.php").read_bytes()).hexdigest()


def mirror_candidate(content, headings, element_id, proposed):
    matches = list(re.finditer(r"<(?P<tag>h[1-6])>(?P<text>[^<>]*)</(?P=tag)>", content))
    if len(matches) != len(headings) or re.sub(r"<h[1-6]>[^<>]*</h[1-6]>", "", content).strip():
        raise CMSFailure("Elementor plain-content mirror is unsupported")
    selected = []
    for match, heading in zip(matches, headings):
        if match["tag"] != heading["tag"] or match["text"] != heading["text"]:
            raise CMSFailure("Elementor mirror differs from raw widget data")
        if heading["element_id"] == element_id:
            selected.append(match)
    if len(selected) != 1:
        raise CMSFailure("Elementor mirror mapping is ambiguous")
    match = selected[0]
    return content[:match.start("text")] + plain(proposed) + content[match.end("text"):]


def render(source, mapping, expected):
    mapping = replace(mapping, current=expected)
    bind_rendered_heading(source["html"], mapping)
    soup = BeautifulSoup(source["html"], "html.parser")
    node = soup.find(attrs={"data-id": mapping.element_id}).find(mapping.tag)
    # Reuse semantic surrounding-page comparison after a fully proven identity.
    marker = "lseo-elementor-verification-target"
    if soup.find(id=marker):
        raise CMSFailure("Reserved verification identity occurs in the page")
    node["id"] = marker
    return rendered({**source, "html": str(soup)}, marker, expected)


def bind_target(source, target, mapping):
    bind_rendered_heading(source["html"], mapping)
    soup = BeautifulSoup(source["html"], "html.parser")
    node = soup.find(attrs={"data-id": mapping.element_id}).find(mapping.tag)
    marker = "lseo-elementor-frozen-target"
    if soup.find(id=marker):
        raise CMSFailure("Reserved target identity occurs in the page")
    node["id"] = marker
    bind_public_target(str(soup), target, marker)


def prepare(state, source, frozen, mapping):
    value = frozen["action"]
    if set(mapping) != {"object_id", "element_id", "metadata_row_id"}:
        raise CMSFailure("Explicit page, metadata row and widget IDs are required")
    if type(mapping["metadata_row_id"]) is not int or mapping["metadata_row_id"] != state["metadata_row_id"]:
        raise CMSFailure("Metadata row assertion differs from fresh independent server evidence")
    m = map_heading(state["elementor_data"], page_id=state["id"], element_id=mapping["element_id"])
    if m.current != value["current"]:
        raise CMSFailure("Widget title differs from the frozen proposal")
    plain(value["current"])
    plain(value["proposed"])
    bind_target(source, frozen.get("target"), m)
    candidate = preview_heading(state["elementor_data"], m, value["proposed"])
    _, spans = _parse(state["elementor_data"])
    start, end = spans[m.path]
    return {"adapter": ADAPTER, "field": FIELD, "element_id": m.element_id,
            "metadata_row_id": state["metadata_row_id"], "mapping": asdict(m),
            "original_title_token": state["elementor_data"][start:end],
            "candidate_data": candidate,
            "candidate_content": mirror_candidate(state["content"], state["headings"], m.element_id, value["proposed"]),
            "rendered_baseline": render(source, m, m.current),
            "validation": "Local candidate built; exact metadata row, widget/ancestor path, raw source, mirror and frozen public target cross-checked against fresh certified endpoint and HTML. Layout needs human inspection."}


def action_mapping(action):
    return map_heading(action["before"]["elementor_data"], page_id=action["object_id"], element_id=action["element_id"])


def verify_raw(state, action, direction):
    expected_data = action["candidate_data"] if direction == "apply" else action["before"]["elementor_data"]
    expected_content = action["candidate_content"] if direction == "apply" else action["before"]["content"]
    if (state["elementor_data"] != expected_data or state["content"] != expected_content
            or state["metadata_row_id"] != action["metadata_row_id"]):
        raise CMSFailure("Elementor raw source, metadata row or mirror differs from the exact candidate")


def request_fields(action, direction):
    return {"adapter": ADAPTER, "contract": CONTRACT, "metadata_row_id": action["metadata_row_id"],
            "element_id": action["element_id"], "path": list(action_mapping(action).path),
            "replacement_token": json.dumps(action["proposed"], ensure_ascii=True) if direction == "apply" else action["original_title_token"]}
