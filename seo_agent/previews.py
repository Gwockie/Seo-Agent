"""Inert local copies of captured pages with exact, review-only proposed changes."""
from __future__ import annotations

import base64
import difflib
import html
import json
import re
from urllib.parse import urljoin

from .appearance import font_css, validate_appearance
from .config import SiteConfig, public_url, within_site
from .storage import historical_date

MAX_PREVIEW = 8 * 1024 * 1024
TAGS = set("body main header footer section article nav aside div span p a h1 h2 h3 h4 h5 h6 ul ol li strong em b i small br hr img figure figcaption table thead tbody tr th td dl dt dd blockquote time".split())
PROPERTIES = set("display position color background-color background-size background-position font-family font-size font-weight font-style line-height letter-spacing text-align text-transform text-decoration width max-width min-width min-height height margin-top margin-right margin-bottom margin-left padding-top padding-right padding-bottom padding-left box-sizing border-radius border-top-width border-top-color border-top-style border-right-width border-right-color border-right-style border-bottom-width border-bottom-color border-bottom-style border-left-width border-left-color border-left-style box-shadow flex-direction flex-wrap align-items justify-content gap row-gap column-gap grid-template-columns grid-template-rows align-self flex-grow flex-shrink flex-basis order object-fit list-style-type white-space overflow-wrap".split())


def raster_asset(content):
    if not 8 <= len(content) <= 1500000:
        raise ValueError("Image exceeds size limit")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "png"
    elif content.startswith(b"\xff\xd8\xff"):
        mime = "jpeg"
    elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        mime = "webp"
    else:
        raise ValueError("Only static PNG/JPEG/WebP images are supported")
    return f"data:image/{mime};base64," + base64.b64encode(content).decode()


def node_text(node):
    if "text" in node:
        return node["text"]
    return "".join(node_text(c) for c in node.get("children", []))


def walk(tree, depth=0):
    if depth > 40 or not isinstance(tree, dict):
        raise ValueError("Invalid page tree")
    yield tree
    for child in tree.get("children", []):
        yield from walk(child, depth + 1)


def validate_preview(value, sid, aid, config):
    if not isinstance(value, dict) or value.get("schema") != 1 or value.get("site_id") != sid or value.get("audit_id") != aid:
        raise ValueError("Preview belongs to a different site/audit")
    if len(json.dumps(value).encode()) > MAX_PREVIEW:
        raise ValueError("Preview exceeds size limit")
    appearance = validate_appearance(value["appearance"], sid, config.url)
    pages = value.get("pages", [])
    if not isinstance(pages, list) or not 1 <= len(pages) <= 6:
        raise ValueError("Invalid preview pages")
    urls = set()
    for page in pages:
        if not within_site(config.url, page["url"]) or page["url"] in urls:
            raise ValueError("Page outside selected site or duplicate page")
        urls.add(page["url"])
        historical_date(page["captured_utc"])
        if type(page["width"]) is not int or not 320 <= page["width"] <= 2000 or not isinstance(page["title"], str) or len(page["title"]) > 1000:
            raise ValueError("Invalid page metadata")
        nodes = list(walk(page["tree"]))
        if len(nodes) > 5000:
            raise ValueError("Page node limit exceeded")
        index = {}
        for node in nodes:
            if "text" in node:
                if not isinstance(node["text"], str) or len(node["text"]) > 100000:
                    raise ValueError("Invalid captured text")
                continue
            if node.get("id") in index or not re.fullmatch(r"r\d{1,5}", node.get("id", "")):
                raise ValueError("Invalid/duplicate captured node")
            index[node["id"]] = node
            if not isinstance(node.get("style", {}), dict) or not isinstance(node.get("children", []), list):
                raise ValueError("Invalid captured style/children")
        actions = page.get("actions", [])
        if not isinstance(actions, list) or not 1 <= len(actions) <= 20:
            raise ValueError("Invalid action list")
        targets = set()
        for action in actions:
            if action.get("kind") not in ("text", "href", "title"):
                raise ValueError("Unsupported preview action")
            for key in ("current", "proposed", "rationale", "confirmations", "validation", "rollback"):
                if not isinstance(action.get(key), str) or not action[key].strip() or len(action[key]) > 8000:
                    raise ValueError("Incomplete exact-action packet")
            target = action.get("node_id", "title")
            if target in targets:
                raise ValueError("Overlapping proposed actions")
            targets.add(target)
            if action["kind"] == "title":
                current = page["title"]
            else:
                node = index.get(target)
                if not node or node.get("tag") not in TAGS:
                    raise ValueError("Action target unavailable")
                if action["kind"] == "text" and "text_child" in action:
                    position = action["text_child"]
                    children = node.get("children", [])
                    if type(position) is not int or not 0 <= position < len(children) or "text" not in children[position]:
                        raise ValueError("Captured text child unavailable")
                    current = children[position]["text"]
                else:
                    current = node_text(node) if action["kind"] == "text" else node.get("href", "")
                if action["kind"] == "href":
                    if node.get("tag") != "a" or not within_site(config.url, urljoin(page["url"], action["proposed"])):
                        raise ValueError("Link action outside selected site")
            if action["kind"] == "text":
                if current.count(action["current"]) != 1:
                    raise ValueError("Current text does not match one captured occurrence")
            elif current != action["current"]:
                raise ValueError("Current value differs from captured page")
        # Reject parent/child edits, which would hide one of the approved values.
        for target in targets - {"title"}:
            descendants = {n.get("id") for n in list(walk(index[target]))[1:]}
            if descendants & targets:
                raise ValueError("Nested proposed actions overlap")
    images = value.get("images", {})
    if not isinstance(images, dict) or len(images) > 20:
        raise ValueError("Invalid image bundle")
    for url, data in images.items():
        if not within_site(config.url, url):
            raise ValueError("Image outside selected site")
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", data)
        if not match or len(data) > 2000100 or raster_asset(base64.b64decode(match[2], validate=True)) != data:
            raise ValueError("Invalid local image")
    return {**value, "appearance": appearance}


def preview_filename(revision):
    if type(revision) is not int or not 1 <= revision <= 20:
        raise ValueError("Invalid preview revision")
    return "review-preview.json" if revision == 1 else f"review-preview-v{revision}.json"


def preview_revisions(store, sid, aid):
    return [revision for revision in range(1, 21) if store.audit_file(sid, aid, "data", preview_filename(revision)).is_file()]


def load_preview(store, sid, aid, *, revision=None):
    audit = store.audit(sid, aid)
    revisions = preview_revisions(store, sid, aid) if revision is None else [revision]
    if not revisions:
        return None
    path = store.audit_file(sid, aid, "data", preview_filename(max(revisions)))
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_PREVIEW:
        raise ValueError("Preview exceeds size limit")
    return validate_preview(json.loads(path.read_text(encoding="utf-8")), sid, aid, SiteConfig.model_validate_json(audit["config"]))


def save_preview(store, sid, aid, value, *, revision=1):
    store.require_private_write()
    audit = store.audit(sid, aid)
    if audit["legacy"]:
        raise ValueError("Historical evidence is immutable")
    value = validate_preview(value, sid, aid, SiteConfig.model_validate_json(audit["config"]))
    path = store.audit_file(sid, aid, "data", preview_filename(revision))
    # New review artifacts cannot replace previous capture evidence.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle)


def difference(before, after, proposed):
    a, b = re.findall(r"\s+|\S+", before), re.findall(r"\s+|\S+", after)
    out = []
    for operation, i, j, k, l in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        text = html.escape("".join(b[k:l] if proposed else a[i:j]))
        if operation != "equal" and text:
            text = '<mark class="added">' + text + "</mark>" if proposed else '<mark class="removed">' + text + "</mark>"
        out.append(text)
    return "".join(out)


def safe_style(style, images):
    out = []
    for key, value in style.items():
        if key in PROPERTIES and isinstance(value, str) and len(value) <= 250 and re.fullmatch(r"[a-zA-Z0-9#.,()%\s'\"+/-]+", value) and not re.search(r"url|expression|javascript|behavior|image-set|attr\(", value, re.I):
            # Fixed/sticky elements must never cover review controls.
            if key == "position" and value in ("fixed", "sticky"):
                value = "static"
            out.append(key + ":" + value)
    background = style.get("background-image", "")
    match = re.fullmatch(r"url\(['\"]?([^)'\"]+)['\"]?\)", background)
    if match and match[1] in images:
        out.append("background-image:url('" + images[match[1]] + "')")
    return ";".join(out)


def page_document(bundle, page, *, proposed=False, highlights=True):
    actions = {a.get("node_id"): a for a in page["actions"] if a["kind"] != "title"}
    images = bundle.get("images", {})
    def render(node):
        if "text" in node:
            return html.escape(node["text"])
        tag = node.get("tag", "")
        if tag not in TAGS:
            return ""  # Scripts, forms, custom elements, SVG, embeds stay absent.
        if node.get("style", {}).get("width") == "1px" and node.get("style", {}).get("position") == "absolute":
            return ""  # Offscreen accessibility text is not a visible page region.
        if tag == "body":
            tag = "div"
        action = actions.get(node["id"])
        content = "".join(render(c) for c in node.get("children", []))
        cls = ""
        if action and action["kind"] == "text":
            before = node["children"][action["text_child"]]["text"] if "text_child" in action else node_text(node)
            after = before.replace(action["current"], action["proposed"], 1)
            changed = difference(before, after, proposed) if highlights else html.escape(after if proposed else before)
            content = "".join(changed if i == action["text_child"] else render(c) for i, c in enumerate(node["children"])) if "text_child" in action else changed
        elif action and highlights:
            cls = ' class="link-change"'
            destination = action["proposed"] if proposed else action["current"]
            content += '<small class="destination">Link destination: ' + html.escape(destination) + "</small>"
        attributes = ' style="' + html.escape(safe_style(node.get("style", {}), images), quote=True) + '"'
        if tag == "img":
            src = images.get(node.get("src"))
            return '<img alt="' + html.escape(node.get("alt", ""), quote=True) + '"' + attributes + (' src="' + src + '"' if src else "") + ">"
        if tag in ("br", "hr"):
            return "<" + tag + attributes + ">"
        # No original IDs, hrefs, event handlers or attributes are copied.
        return "<" + tag + attributes + cls + ">" + content + "</" + tag + ">"
    csp = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'"
    return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="' + csp + '"><style>' + font_css(bundle["appearance"]) + f"""
    html {{background:#fff}} body {{margin:0;width:{page['width']}px;zoom:calc(100vw / {page['width']}px)}}
    * {{box-sizing:border-box}} img {{max-width:100%}} a {{cursor:default}}
    mark.added {{background:#dcfce7;color:#14532d;border-bottom:3px solid #15803d}}
    mark.removed {{background:#fee2e2;color:#7f1d1d;border-bottom:3px solid #b91c1c}}
    .link-change {{outline:3px solid #a16207;outline-offset:3px}}
    .destination {{display:block!important;background:#fef3c7;color:#422006;font:14px/1.4 Arial!important;padding:6px;overflow-wrap:anywhere}}
    </style></head><body>""" + render(page["tree"]) + "</body></html>"


def preview_frame(document):
    # The inner sandbox has no permissions, including same-origin and scripts.
    return '<iframe title="Local page review preview" sandbox="" referrerpolicy="no-referrer" style="border:1px solid #d6d3d1;border-radius:8px;width:100%;height:850px" srcdoc="' + html.escape(document, quote=True) + '"></iframe>'
