"""Session-only declaration editor for the saved-capture verifier."""
import json
from typing import get_args

import streamlit as st

from . import publication_verification as verification
from .storage import Store


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def _capture(store, sid, url, label, selected, key):
    with store.db() as db:
        rows = {r["id"]: dict(r) for r in db.execute(
            "SELECT id, url, checked, status FROM public_snapshots WHERE site_id=? AND url=? ORDER BY checked, id",
            (sid, url))}
    # Keep an imported or previously selected reference even when it is missing.
    selected = st.session_state.get(key, selected)
    options = [None, *rows]
    if selected is not None and selected not in options:
        options.append(selected)

    def name(identity):
        if identity is None:
            return "Select an exact saved capture"
        row = rows.get(identity)
        return (f"{identity} · {row['checked']} · {row['status']}" if row else
                identity + " · unavailable for this exact site and URL")

    identity = st.selectbox(label, options, index=options.index(selected), format_func=name, key=key)
    if identity:
        st.text(label + ": " + url + "\n" + name(identity))
    return identity


def render(store, sid):
    # A second read-only handle prevents this screen from writing to the journal.
    store = Store(store.root, read_only=True)
    prefix = sid + ":publication_verification:"
    st.subheader("Publication verification")
    st.caption("Saved static public evidence only. This report is not publication approval or a verified CMS receipt. It does not establish CMS state, authorship, browser behavior or Google indexing.")
    st.info("Declare every affected URL and effect explicitly, including shared navigation on other pages. Shared-effect scope is not inferred. Captures are never refreshed or replaced automatically.")
    st.text("Site: " + store.site(sid).url + "\nSite ID: " + sid)

    upload = st.file_uploader("Import expectations JSON file", type=["json"], key=prefix + "upload")
    pasted = st.text_area("Or paste expectations JSON", key=prefix + "import_text")
    if st.button("Import expectations", key=prefix + "import"):
        try:
            raw = upload.getvalue() if upload is not None else pasted
            draft = verification.Expectations.model_validate(json.loads(raw)).model_dump()
            if draft["site_id"] != sid:
                raise ValueError("Expectations must belong to the explicitly selected site")
            st.session_state[prefix + "draft"] = draft
            st.session_state[prefix + "generation"] = st.session_state.get(prefix + "generation", 0) + 1
            st.session_state.pop(prefix + "result", None)
            st.success("Imported exact references and expectations into this session.")
        except (ValueError, TypeError, UnicodeError) as exc:
            st.error("Import rejected; existing form preserved.")
            st.text(str(exc))

    draft = st.session_state.get(prefix + "draft", {"pages": []})
    generation = str(st.session_state.get(prefix + "generation", 0))
    key = prefix + generation + ":"
    count = st.number_input("Number of declared pages", min_value=1, max_value=20,
                            value=max(1, len(draft["pages"])), key=key + "pages")
    kinds = list(get_args(verification.Effect.model_fields["kind"].annotation))
    pages = []
    for index in range(count):
        page = draft["pages"][index] if index < len(draft["pages"]) else {}
        pk = key + str(index) + ":"
        with st.expander(f"Declared page {index + 1}", expanded=True):
            url = st.text_input("Exact page URL", value=page.get("url", ""), key=pk + "url", max_chars=2048)
            before = _capture(store, sid, url, "Before capture", page.get("before_snapshot_id"), pk + "before")
            after = _capture(store, sid, url, "After capture", page.get("after_snapshot_id"), pk + "after")
            effects = page.get("effects", [])
            effect_count = st.number_input("Number of expected effects", min_value=1, max_value=30,
                                           value=max(1, len(effects)), key=pk + "effects")
            edited = []
            for number in range(effect_count):
                effect = effects[number] if number < len(effects) else {}
                ek = pk + str(number) + ":"
                st.text(f"Effect {number + 1}")
                kind = st.selectbox("Effect kind", kinds, index=kinds.index(effect.get("kind", kinds[0])), key=ek + "kind")
                selector = (st.text_input("Exact CSS selector", value=effect.get("selector") or "", key=ek + "selector", max_chars=400)
                            if kind in verification.TEXT_KINDS else None)
                old = st.text_area("Expected before", value=effect.get("before", ""), key=ek + "before", max_chars=8000)
                new = st.text_area("Expected after", value=effect.get("after", ""), key=ek + "after", max_chars=8000)
                edited.append({"kind": kind, "selector": selector, "before": old, "after": new})
            pages.append({"url": url, "before_snapshot_id": before, "after_snapshot_id": after, "effects": edited})
    declaration = {"schema_version": "seo-publication-expectations/1", "site_id": sid, "pages": pages}
    st.session_state[prefix + "draft"] = declaration
    try:
        valid = verification.Expectations.model_validate(declaration).model_dump()
    except ValueError:
        valid = None
    st.download_button("Download expectations JSON", _json(valid) if valid else "", "publication-expectations.json",
                       "application/json", disabled=valid is None, key=prefix + "export")
    if st.button("Run read-only verifier", key=prefix + "run"):
        st.session_state.pop(prefix + "result", None)
        try:
            result = verification.report(store, declaration)
            st.session_state[prefix + "result"] = {"declaration": declaration, "report": result}
        except (ValueError, TypeError) as exc:
            st.error("Verification could not run. Review the declaration; saved evidence is unchanged.")
            st.text(str(exc))
    saved = st.session_state.get(prefix + "result")
    if not saved:
        return
    if declaration != saved["declaration"]:
        st.warning("The form changed. Run the verifier again to view and download a report for these expectations.")
        return
    result = saved["report"]
    st.text("Expectations SHA-256: " + result["expectations_sha256"])
    for page in result["pages"]:
        st.text("Results for " + page["url"])
        for side in ("before", "after"):
            st.text(side.capitalize() + " capture reference")
            st.json(page[side + "_capture"])
        for effect in page["effects"]:
            expectation = effect["expectation"]
            st.text(expectation["kind"] + (" · " + expectation["selector"] if expectation["selector"] else ""))
            status = effect["status"]
            message = {"matches_expectation": "Matches expectation: both observed values equal their respective expectations.",
                       "mismatch": "Mismatch: at least one observed value differs from its expectation.",
                       "unavailable": "Unavailable: the saved evidence cannot support this comparison."}[status]
            {"matches_expectation": st.success, "mismatch": st.error, "unavailable": st.warning}[status](message)
            for side in ("before", "after"):
                observed = effect[side]
                st.text(side.capitalize() + " expected: " + _json(expectation[side]) +
                        "\n" + side.capitalize() + " observed: " + _json(observed["value"]))
                if observed.get("reason"):
                    st.text(side.capitalize() + ": " + observed["reason"])
            if effect.get("reason"):
                st.text(effect["reason"])
    st.download_button("Download verification report JSON", _json(result), "publication-verification.json",
                       "application/json", key=prefix + "download_report")
