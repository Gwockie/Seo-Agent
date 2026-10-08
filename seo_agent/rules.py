"""Transparent trusted diagnostics. Every finding uses this site's current evidence."""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

from .config import resolve_rules, public_url, within_site, service_terms
from .metrics import classify


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    if path.stat().st_size > 40 * 1024 * 1024:
        raise ValueError("Evidence file exceeds read limit")
    try:
        return pd.read_csv(path).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def generate(config, site_id, audit_id, frames, resolved=None):
    resolved = resolved or resolve_rules(config)
    registry = resolved["rules"]
    findings = []
    priority_pages = {p.landing_page for p in config.phrases if p.active and p.landing_page} - set(config.exclusions)

    def add(rule, priority, category, url, query, detail, action, file, row, impact=4, confidence=4, effort=2):
        if not registry[rule]["settings"]["enabled"]:
            return
        findings.append({"site_id": site_id, "audit_id": audit_id, "rule": rule, "rule_version": registry[rule]["version"],
            "profile_version": resolved["profile_version"], "industry": config.industry,
            "priority": priority, "category": category, "url": url, "query": query, "detail": detail,
            "impact": impact, "confidence": confidence, "effort": effort, "proposed_action": action,
            "confirmations": resolved["guidance"]["confirmations"], "evidence": [{"file": file, "row": int(row) + 2}],
            "measurement": "After separately approved implementation, compare equal complete final web-search windows for this query/page; inspect canonical/indexing and qualified clicks separately. Observations do not establish causality.",
            "approval": "Exact-action human approval required; recommendation state grants no website permission."})

    crawl = frames.get("crawl", pd.DataFrame())
    inspections = frames.get("url_inspection", pd.DataFrame())
    qp = frames.get("gsc_query_page", pd.DataFrame())
    for i, row in crawl.iterrows():
        url = str(row.get("final_url") or row.get("url"))
        source = str(row.get("url"))
        is_priority = url in priority_pages or source in priority_pages
        if is_priority:
            directive = (str(row.get("robots_meta", "")) + " " + str(row.get("x_robots_tag", ""))).casefold()
            if "noindex" in directive or str(row.get("status")) == "blocked_by_robots":
                add("indexing", "P0", "indexing", url, "", f"Observed restriction: {directive or row.get('status')}", "Confirm this service page is intended to be indexed; prepare an exact directive/robots change for approval.", "crawl.csv", i, confidence=5)
            canonical = str(row.get("canonical", ""))
            if canonical and canonical != url:
                add("canonical", "P0", "canonical", url, "", f"Page canonical is {canonical}", "Review intended canonical and redirects against Google's inspection before proposing a correction.", "crawl.csv", i)
            if str(row.get("status")) == "200" and "text/html" in str(row.get("content_type", "")):
                heading = " ".join(str(row.get(k, "")) for k in ("title", "h1", "h2")).casefold()
                phrases = [p for p in config.phrases if p.active and p.landing_page in {url, source}]
                missing = []
                for p in phrases:
                    terms = p.related_terms + service_terms(config, p.group)
                    if terms and not any(t.casefold() in heading for t in terms):
                        missing.append(p.group)
                location_missing = config.location and config.location.casefold() not in heading
                if missing or location_missing:
                    detail = f"Title: {row.get('title', '')}; H1: {row.get('h1', '')}. Missing configured heading signals: {sorted(set(missing))}; location: {bool(location_missing)}. This is a content-review lead, not proof of ranking cause."
                    add("relevance", "P1", "content/local relevance", url, "", detail, "Draft a factual title/heading that identifies the configured service and genuine location, subject to confirmation. Near-me phrases express intent; do not repeat them literally.", "crawl.csv", i, confidence=3)
                    if findings and findings[-1]["rule"] == "relevance":
                        service = next((term for p in phrases for term in p.related_terms + service_terms(config, p.group)), "")
                        findings[-1]["current_title"] = str(row.get("title", ""))
                        findings[-1]["proposed_title"] = (service + (" in " + config.location if config.location else "") + " | " + config.name) if service else "Pending service wording confirmation"
                        findings[-1]["replacement_status"] = "Local proposal only; confirm actual service/location and business wording before exact-action approval."
                    if config.industry == "psychology" and registry["relevance"]["settings"]["enabled"]:
                        add("clinical_review", "P1", "clinical factual review", url, "", detail, "Before changing this service page, obtain clinician confirmation of services, audience, assessment process and any clinical claims; use only this site's confirmed facts.", "crawl.csv", i, confidence=5)
        try:
            links = json.loads(row.get("internal_link_urls") or "[]")
        except (ValueError, TypeError):
            links = []
        for dest in links[:2000]:
            if not crawl.empty and "url" in crawl:
                observed = crawl[crawl.url.eq(dest)]
                if not observed.empty and str(observed.iloc[0].get("status")) in {"404", "410"}:
                    add("broken_link", "P2", "internal linking", source, "", f"Source links to {dest}; crawled destination HTTP {observed.iloc[0]['status']}", "Review the intended destination and propose repair of this specific source link.", "crawl.csv", i, confidence=5)
                    findings[-1]["evidence"].append({"file": "crawl.csv", "row": int(observed.index[0]) + 2}) if findings and findings[-1]["rule"] == "broken_link" else None
    for i, row in inspections.iterrows():
        url = str(row.get("url", ""))
        if url not in priority_pages or row.get("error"):
            continue
        if str(row.get("verdict")) in {"FAIL", "NEUTRAL"} or str(row.get("indexing_state", "")) in {"BLOCKED_BY_META_TAG", "BLOCKED_BY_HTTP_HEADER"}:
            add("indexing", "P0", "indexing", url, "", f"Google verdict {row.get('verdict')}; coverage {row.get('coverage_state')}; indexing {row.get('indexing_state')}", "Diagnose Google's recorded restriction and last crawl date before proposing any website action.", "url_inspection.csv", i, confidence=5)
        canonical = row.get("google_canonical")
        if canonical and canonical != url:
            add("canonical", "P0", "canonical", url, "", f"Google canonical: {canonical}; user canonical: {row.get('user_canonical')}", "Review Google/user canonical disagreement and internal links; prepare a scoped correction only if intended canonical is confirmed.", "url_inspection.csv", i, confidence=5)
    for i, row in qp.iterrows():
        query, page = str(row.get("query", "")), str(row.get("page", ""))
        try:
            if not within_site(config.url, page):
                continue
        except ValueError:
            continue
        labels = classify(query, config)
        if not labels["groups"] or labels["branded"]:
            continue
        impressions = float(row.get("impressions", 0) or 0)
        clicks = float(row.get("clicks", 0) or 0)
        position = float(row.get("position", 999) or 999)
        for p in config.phrases:
            matches = p.phrase.casefold() == query.casefold() or (not labels["exact"] and p.group in labels["groups"])
            if p.active and matches and p.landing_page and p.landing_page != page and impressions >= registry["alignment"]["settings"]["min_impressions"]:
                add("alignment", "P1", "query/page alignment", page, query, f"Observed {impressions:g} impressions, {clicks:g} clicks, position {position:g}; intended {p.landing_page}", f"Review search intent and relevance/internal links for intended page {p.landing_page}. Multiple pages are a review signal, not proof of harmful cannibalization.", "gsc_query_page.csv", i, confidence=3)
                break
        ctr = clicks / impressions if impressions else None
        settings = registry["ctr"]["settings"]
        if impressions >= settings["min_impressions"] and position <= 10 and ctr is not None and ctr < settings["ctr_threshold"]:
            add("ctr", "P2", "CTR review", page, query, f"Sample: {clicks:g} clicks / {impressions:g} impressions = {ctr:.2%}; position {position:g}. Heuristic threshold, not evidence of bad copy.", "Review the actual search snippet and query intent; draft a factually accurate title/description for exact-action approval.", "gsc_query_page.csv", i, impact=3, confidence=2)
    # Deduplicate equivalent signals without merging any external site's context.
    unique = {}
    for finding in findings:
        unique[(finding["rule"], finding["url"], finding["query"], finding["detail"])] = finding
    return sorted(unique.values(), key=lambda f: (f["priority"], -f["impact"]))


LIMITATIONS = "Query exports contain top visible rows and omit anonymized queries; missing rows do not prove zero demand. Source failures and empty exports are distinct. Average organic position is not a map-pack ranking. Qualified inquiries are not supplied by these exports. SEO-plugin scores are not success metrics."


def write_reports(config, site_id, audit_id, data, reports, findings, manifest):
    from .metrics import totals, query_groups
    reports = Path(reports)
    reports.mkdir(parents=True, exist_ok=True)
    current = totals(read_csv(Path(data) / "gsc_totals.csv")) if manifest.get("stages", {}).get("gsc_current", {}).get("status") == "complete" else totals(pd.DataFrame())
    header = f"Site: {config.name}\nSite ID: {site_id}; audit: {audit_id}\nProfile: {config.industry} {config.profile_version}\nStatus: {manifest['status']}\nWindows (Pacific, final web): {manifest['windows']}\n\n"
    summary = ["# Executive summary", header, f"Property metrics (byProperty): {current}", LIMITATIONS, "", "## Why visibility may be underperforming", "Observed diagnostic leads below require human interpretation; this audit cannot establish ranking causes or off-site competition."]
    summary.insert(2, "Configured active targets: " + "; ".join(p.phrase for p in config.phrases if p.active))
    if findings:
        summary += [f"- {f['priority']} {f['category']}: {f['detail']} [{f['evidence'][0]['file']} row {f['evidence'][0]['row']}]" for f in findings[:5]]
    else:
        summary += ["No supported rule findings from the available evidence. Missing evidence does not establish a clean site."]
    summary += ["", "## Does Google understand the configured offering?", "Target query/page observations are available in gsc_query_page.csv. Alignment findings indicate review opportunities; absent queries are inconclusive.", "", "## Indexing", "Review crawl directives and Google URL Inspection evidence. Uninspected pages are unknown; a public fetch does not prove indexing.", "", "## Five highest-value opportunities", *[f"{i+1}. {f['proposed_action']} ({f['rule']} {f['rule_version']})" for i, f in enumerate(findings[:5])], "If fewer than five are supported, collect missing evidence before inventing further findings.", "", "## On-site and off-site", "The observed canonical, link, relevance and snippet leads can be reviewed on-site. Off-site prominence/competition require separate evidence; this app supplies no backlink or map-pack data.", "", "## Source status", json.dumps(manifest.get("stages", {}), indent=2)]
    recs = ["# Recommendations", header, "Review/implementation state is separate from exact-action approval.", LIMITATIONS]
    proposed = ["# Proposed edits", header, "Local drafts only. No external website or Search Console change is authorized by this report."]
    for f in findings:
        ref = "; ".join(f"{r['file']} row {r['row']}" for r in f["evidence"])
        recs += ["", f"## {f['priority']} — {f['category']}", f"URL: {f['url']}; query: {f['query']}", f"Rule: {f['rule']} {f['rule_version']}; evidence: {ref}", f"Evidence: {f['detail']}", f"Impact/confidence/effort: {f['impact']}/{f['confidence']}/{f['effort']}", f"Suggested change: {f['proposed_action']}", f"Confirmations: {' '.join(f['confirmations'])}", f"Measure: {f['measurement']}"]
        proposed += ["", f"## {f['url']}", f"Current evidence: {f['detail']}", f"Proposed action/replacement direction: {f['proposed_action']}", "Exact replacement: pending local drafting and factual review; no unconfirmed claims supplied.", f"Rationale/evidence: {ref}; {f['rule']} {f['rule_version']}", f"Factual confirmation: {' '.join(f['confirmations'])}", "Before approval: enumerate exact current/proposed values, affected URL/setting, validation and rollback plan. Wait for explicit human approval of those exact actions."]
        if "proposed_title" in f:
            proposed += [f"Current title: {f['current_title']}", f"Proposed title replacement: {f['proposed_title']}", f["replacement_status"]]
    for name, lines in (("executive-summary", summary), ("recommendations", recs), ("proposed-edits", proposed)):
        (reports / (name + ".md")).write_text("\n\n".join(lines), encoding="utf-8")
    # Legacy mechanical summary name remains usable.
    (reports / "snapshot.md").write_text("\n\n".join(summary), encoding="utf-8")
