"""Verify an explicitly scoped title transition in deterministic HTML captures."""
from dataclasses import dataclass
from hashlib import sha256

from bs4 import BeautifulSoup, NavigableString
from soupsieve import SelectorSyntaxError

MAX_CAPTURE_BYTES = 2_000_000
TEXT_ELEMENTS = {"title", "h1", "h2", "h3", "h4", "h5", "h6", "a", "span"}


@dataclass(frozen=True)
class TitleEffect:
    selector: str
    count: int = 1
    prefix: str = ""
    suffix: str = ""


def _whole_text_effects(source, title, effects):
    soup = BeautifulSoup(source.decode("utf-8"), "html.parser")
    if not soup.html or not soup.head or not soup.body:
        raise ValueError("A complete captured HTML document is required")
    positions = {id(node): position for position, node in enumerate(soup.find_all(True))}
    matched = {}
    for effect in effects:
        try:
            nodes = soup.select(effect.selector, limit=effect.count + 1)
        except SelectorSyntaxError as exc:
            raise ValueError("Invalid title-effect selector") from exc
        if len(nodes) != effect.count:
            raise ValueError("Title-effect selector matched a different number of elements: " + effect.selector)
        expected = effect.prefix + title + effect.suffix
        for node in nodes:
            position = positions[id(node)]
            if (node.name not in TEXT_ELEMENTS or (node.name == "title" and node.parent is not soup.head)
                    or len(node.contents) != 1 or type(node.contents[0]) is not NavigableString
                    or node.contents[0] != expected or position in matched):
                raise ValueError("Title-effect text, placement or selector overlap differs: " + effect.selector)
            matched[position] = (node.name, effect)
    return matched


def verify_title_effects(before, after, *, current, proposed, effects):
    """Check whole text elements and reject any other captured byte changes.

    The caller supplies one reviewed effect list for each captured page. Selectors
    must identify all changed text and may distinguish repeated navigation labels
    by their widget, menu item and link. This is a capture comparison only.
    """
    if any(type(source) is not bytes or not 0 < len(source) <= MAX_CAPTURE_BYTES for source in (before, after)):
        raise ValueError("Supply two bounded UTF-8 HTML captures")
    if (current == proposed or any(not isinstance(title, str) or not title.strip() or len(title) > 500
                                   or any(c in "<>&" or ord(c) < 32 for c in title)
                                   for title in (current, proposed))):
        raise ValueError("Distinct literal title text is required")
    if len(effects) > 30 or any(not isinstance(e, TitleEffect) or type(e.count) is not int or not 1 <= e.count <= 50
                               or not 1 <= len(e.selector.strip()) <= 400 or len(e.prefix) + len(e.suffix) > 500
                               for e in effects):
        raise ValueError("Supply a bounded list of explicit title effects")
    old, new = current.encode("utf-8"), proposed.encode("utf-8")
    total = sum(effect.count for effect in effects)
    if before.count(old) != total or before.replace(old, new) != after:
        raise ValueError("Captured change differs from the declared literal title substitutions")
    matched = _whole_text_effects(before, current, effects)
    if matched != _whole_text_effects(after, proposed, effects):
        raise ValueError("Title-effect selectors resolved to different elements")
    # Probe the exact byte substitutions independently of selector evaluation.
    # An entity-decoded old title cannot hide a substitution in an attribute or
    # an unrelated node, even when both captures resolve to plausible text.
    marker = "LSEO-TITLE-" + sha256(before).hexdigest()
    probe = BeautifulSoup(before.replace(old, marker.encode("ascii")).decode("utf-8"), "html.parser")
    probe_nodes = probe.find_all(True)
    for position, (tag, effect) in matched.items():
        if (position >= len(probe_nodes) or probe_nodes[position].name != tag
                or len(probe_nodes[position].contents) != 1
                or type(probe_nodes[position].contents[0]) is not NavigableString
                or probe_nodes[position].contents[0] != effect.prefix + marker + effect.suffix):
            raise ValueError("Literal title substitution falls outside the declared text")
    return {"before_sha256": sha256(before).hexdigest(), "after_sha256": sha256(after).hexdigest(),
            "substitutions": total}
