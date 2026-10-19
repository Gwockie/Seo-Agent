"""Action-bound, offline Elementor candidates. Never a writer certificate or approval.

The strict synthetic publisher mapper is intentionally unchanged. This inspector
can preserve unrelated dynamic/shared siblings while reporting their unresolved
effects. Selected dynamic/shared/rich/linked targets remain unavailable.
"""
from dataclasses import asdict
import hashlib
import json
import re

from . import discovery as d, tracking as t
from .coordination import run_lock, workspace_lock
from .elementor import HeadingMapping, _parse, _unlinked, bind_rendered_heading
from .elementor_publishing import plain, bind_target
from .proposal_review import context_binding
from .page_tracking import latest_snapshot, observed_value
from .publishing import mapped_url

KIND = "elementor_candidate"


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def inspect_heading(raw, page_id, element_id):
    """Inspect only; returned mappings must never be passed to a publisher."""
    if type(page_id) is not int or page_id < 1 or not isinstance(element_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", element_id):
        raise ValueError("Explicit page and widget identities are required")
    data, spans = _parse(raw)
    identities, selected, dependencies = set(), [], []

    def walk(nodes, path, ancestors, ancestor_dependencies):
        if not isinstance(nodes, list):
            raise ValueError("Malformed Elementor document")
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise ValueError("Malformed Elementor node")
            identity, kind = node.get("id"), node.get("elType")
            settings, children = node.get("settings"), node.get("elements")
            if (not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identity)
                    or identity in identities or kind not in ("container", "section", "column", "widget")
                    or not (isinstance(settings, dict) or settings == []) or not isinstance(children, list)):
                raise ValueError("Malformed or duplicate Elementor identity")
            identities.add(identity)
            settings = settings or {}
            own = [name for name, present in (
                ("dynamic", settings.get("__dynamic__")), ("global_style", settings.get("__globals__")),
                ("shared_template", node.get("templateID") or settings.get("template_id") or node.get("widgetType") in ("global", "template"))) if present]
            here = path + (i,)
            if own:
                dependencies.append({"element_id": identity, "path": list(here), "kinds": own})
            if identity == element_id:
                if kind != "widget" or node.get("widgetType") != "heading" or children:
                    raise ValueError("Selected widget is not a leaf heading")
                if own or ancestor_dependencies:
                    raise ValueError("Selected heading or ancestor has dynamic/shared/global dependencies")
                if not _unlinked(settings.get("link")):
                    raise ValueError("Selected heading is linked")
                if settings.get("header_size") not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    raise ValueError("Heading level is implicit or unsupported; independently certify the installed default first")
                title = plain(settings.get("title"))
                selected.append(HeadingMapping(page_id, identity, ancestors, here + ("settings", "title"),
                                               settings["header_size"], title, _sha(raw)))
            walk(children, here + ("elements",), ancestors + (identity,), ancestor_dependencies + own)

    walk(data, (), (), [])
    if len(selected) != 1:
        raise ValueError("Selected heading identity is missing")
    mapping = selected[0]
    return mapping, spans[mapping.path], dependencies


def current_action(store, sid, action_id, revision):
    row = t.action(store, sid, action_id, revision)
    latest = next(a for a in t.actions(store, sid) if a["action_id"] == action_id)
    if latest["revision"] != revision:
        raise ValueError("Select the latest saved action revision")
    return row


def dependencies_current(store, sid, cid, data):
    try:
        row = current_action(store, sid, data["action_id"], data["revision"])
        if row["audit_id"] != data["audit_id"] or d.digest(row["payload"]) != data["action_sha256"]:
            return False
        if context_binding(store, sid, row) != data.get("action_context"):
            return False
        for kind, field in (("public", "public_evidence_id"), ("administrator_export", "administrator_evidence_id")):
            parent = d.latest(store, sid, cid, kind)
            if (parent["id"] if parent else None) != data[field]:
                return False
        return True
    except (ValueError, KeyError, StopIteration):
        return False


def prepare(store, sid, cid, action_id, revision, page_id, element_id):
    """Save an exact inert candidate or precise blockers, using existing evidence.

    No requests, CMS writes, edits to proposals, factual confirmations or approvals.
    A blocked report is useful even when hosting access has not yet been supplied.
    """
    store.require_private_write()
    if type(page_id) is not int or page_id < 1 or not isinstance(element_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", element_id):
        raise ValueError("Explicit page and widget identities are required")
    with run_lock(workspace_lock(store.root)):
        c = d.active(store, sid, cid)
        c["_collection_scope"] = d.scope(store, sid, c)
        row = current_action(store, sid, action_id, revision)
        value = row["payload"]
        url = mapped_url(c, store.site(sid).url, value["url"])
        public, admin = (d.latest(store, sid, cid, kind) for kind in ("public", "administrator_export"))
        report = {"schema": "elementor-local-candidate/1", "action_id": action_id, "revision": revision,
            "audit_id": row["audit_id"], "action_sha256": d.digest(value), "action_context": context_binding(store, sid, row),
            "source_url": value["url"], "url": url,
            "page_id": page_id, "element_id": element_id, "current": value["current"], "proposed": value["proposed"],
            "confirmations": value["confirmations"], "public_evidence_id": public["id"] if public else None,
            "administrator_evidence_id": admin["id"] if admin else None, "candidate": None,
            "preparation_blockers": [], "publication_blockers": [
                "The actual installed stack needs a separately reviewed writer/effect contract and representative integration tests.",
                "Independent runtime metadata identity, mirror/excerpt, shared/kit settings, generated assets, hooks and scoped host cache effects remain required.",
                "Fresh verified isolated staging, human factual confirmation, frozen proposal approval, separate CMS authorization and explicit Apply remain required."],
            "publishing_compatible": False, "staging_validated": False, "production_ready": False}
        blocked = report["preparation_blockers"]
        if value["action_kind"] != "text":
            blocked.append("This candidate supports a saved heading text action only")
        if not public:
            blocked.append("Refresh current independent public REST/rendered evidence")
        if not admin:
            blocked.append("Collect current protected administrator page/raw metadata-row evidence and installation identity")
        snapshot = latest_snapshot(store, sid, value["url"])
        # A clone's newer capture cannot supersede a known observation of its
        # production source. For production, a newer independent read can do so.
        if snapshot and public and (c["environment"] != "production" or
                d.timestamp(snapshot["checked"]) >= d.timestamp(public["payload"]["body"]["observed_utc"])):
            if snapshot["status"] != "complete":
                blocked.append("Latest source-page observation is unavailable; refresh and reconcile source evidence")
            elif observed_value(snapshot["payload"]["values"], value, target=report["action_context"]["target"],
                                html=snapshot["payload"]["html"]) != value["current"]:
                blocked.append("Latest source-page observation conflicts with the saved action; refresh and reconcile discovery and proposal evidence")
        if not blocked:
            pd, ad = (r["payload"]["body"]["data"] for r in (public, admin))
            page = next((p for p in ad.get("pages", []) if p["id"] == page_id and p["type"] == "page"), None)
            rest = next((p for p in pd.get("pages", []) if p["id"] == page_id), None)
            capture = next((p for p in pd.get("captures", []) if p["page_id"] == page_id), None)
            if (not page or not rest or not capture or any(p["url"] != url for p in (page, rest, capture))
                    or page["template"] != rest["template"] or page["raw_content"] is None or page["raw_excerpt"] is None):
                blocked.append("Exact action URL, public page/template, raw mirror or explicit excerpt cannot be reconciled")
            else:
                report["shared_ids"] = page["shared_ids"]
                metadata = [m for m in page["metadata"] if m["key"] == "_elementor_data"]
                if len(metadata) != 1:
                    blocked.append("One exact administrator-sourced Elementor metadata row is required")
                else:
                    try:
                        raw = metadata[0]["value"]
                        mapping, (start, end), dependencies = inspect_heading(raw, page_id, element_id)
                        if mapping.current != value["current"]:
                            raise ValueError("Raw heading differs from the saved action; revise that action using fresh evidence")
                        proposed = plain(value["proposed"])
                        if proposed == mapping.current:
                            raise ValueError("Saved action has no heading change")
                        bind_rendered_heading(capture["html"], mapping)
                        target = report["action_context"]["target"]
                        bind_target({"html": capture["html"]}, target, mapping)
                        report["target"] = target
                        replacement = json.dumps(proposed, ensure_ascii=True)
                        candidate = raw[:start] + replacement + raw[end:]
                        report["candidate"] = {"mapping": asdict(mapping), "metadata_row_id": metadata[0]["row_id"],
                            "metadata_identity_certainty": "administrator_asserted", "source_sha256": _sha(raw),
                            "candidate_sha256": _sha(candidate), "data": candidate,
                            "original_title_literal": raw[start:end], "replacement_title_literal": replacement,
                            "preserved_dependencies": dependencies, "template": page["template"],
                            "mirror_sha256": _sha(page["raw_content"]), "excerpt_sha256": _sha(page["raw_excerpt"]),
                            "scope": "Offline JSON only: replace exactly the selected string. No CMS mirror, timestamps, cache, asset or database changes.",
                            "inverse": "Offline only: restore the captured original string at this exact path while the entire candidate hash matches. CMS rollback needs its own approved effect contract."}
                    except ValueError as e:
                        # Parser and mapping errors are deliberately fixed messages, never raw input.
                        blocked.append(str(e))
        report["level"] = "candidate_prepared" if report["candidate"] else "blocked"
        observed = min([r["payload"]["body"]["observed_utc"] for r in (public, admin) if r] or [d.utc_now()])
        return d._save(store, sid, c, KIND, report, observed=observed,
                       source="Offline evaluation of the exact saved action against current discovery evidence",
                       certainty="cross_checked_not_certified")


def inverse(raw, candidate):
    """Restore an offline candidate byte-for-byte; never an authorized CMS inverse."""
    if _sha(raw) != candidate["candidate_sha256"]:
        raise ValueError("Offline candidate changed; refuse inverse")
    _, spans = _parse(raw)
    path = tuple(candidate["mapping"]["path"])
    if path not in spans:
        raise ValueError("Offline candidate path changed; refuse inverse")
    start, end = spans[path]
    if raw[start:end] != candidate["replacement_title_literal"]:
        raise ValueError("Offline candidate title changed; refuse inverse")
    restored = raw[:start] + candidate["original_title_literal"] + raw[end:]
    if _sha(restored) != candidate["source_sha256"]:
        raise ValueError("Offline inverse differs from captured source")
    return restored
