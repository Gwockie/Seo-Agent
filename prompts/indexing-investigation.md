# Follow-up agent: deep investigation of URLs unknown to Google

Work in `C:\Users\keyse\.codex\worktrees\6550\local-seo-agent` for `https://meadowandmindpsychology.com/`.

Investigate every audited URL reported as unknown to Google, establish likely causes with evidence and complete a reviewable local remediation proposal. Do not stop at a generic indexing checklist or a plan. No website implementation is authorized.

## Read first

- AGENTS.md, README.md, LOCAL_SEO_ROADMAP.md and docs/LOCAL_DEVELOPMENT.md.
- docs/audits/2026-10-05-public/README.md and its linked audit deliverables; preserve this historical baseline.
- docs/audits/2026-10-05-followup/README.md.
- seo_agent/auth.py, gsc.py, crawl.py and __main__.py.
- If present in this actual checkout: data/20261005T220630Z/ and reports/20261005T220630Z/, especially manifest/window, crawl, Inspection, additional/repeat Inspection, concern-verification, sitemap metadata and gsc-supplement/evidence-index/validation. These are ignored and do not accompany clones; do not assume access or synthesize missing evidence.

## Evidence starting point

Individual therapy is the priority service URL: Inspection twice reported “URL is unknown to Google”, while public HTTP 200, index/follow, self-canonical, existing internal links and current page-sitemap inclusion were observed. The cause remains unresolved. Unknown state does not establish a robots block, noindex, wrong canonical or fetch failure.

Derive the complete unknown list from actual Inspection exports. Previously observed examples are /individual-therapy/, /affordable-therapy-pennsylvania/, /category/psychology/, /?elementskit_template=faqs, /?elementskit_template=home-2 and /locations.kml. Distinguish desired service pages from archive/layout/non-HTML artifacts. The separate /home-2/ path was inspected as a redirect with the homepage canonical; do not conflate it with the query-template URL or propose a new redirect automatically.

## Investigation

1. Inventory exact URLs, public final URLs/redirect hops, content types, purpose, intended indexability, Inspection verdict/coverage/crawl/fetch/index directives and both canonicals. Preserve absent/UNSPECIFIED values as unavailable. Record retrieval times and source age; a historical indexed report is not a live Google fetch.
2. Use robots-respecting public read-only GETs and the existing helper to check host/HTTPS/slash/query variants, redirects, robots/meta/HTTP directives, rendered or source content, soft-404/duplicate clues, sitemap entries and internal links from indexed pages. Avoid infinite URL variants and form submissions. Public browser rendering is allowed if available; no admin/editor access or autosaves.
3. Evaluate discovery depth, sitemap currency and the difference between sitemap membership and Google's reported discovery. Old sitemap metadata is a clue, not proof of a broken sitemap. Separate header noindex on XML/template resources from service-page directives.
4. Reuse the existing local .venv and read-only token when valid. Never print credentials or borrow tokens from another project. Preserve conflicting/invalid files. Run sites to verify the exact appropriate property before new API calls; prefer a matching domain property only if actually returned. Request only https://www.googleapis.com/auth/webmasters.readonly. Use the existing indexed-state Inspection helper for relevant exact URLs; do not request indexing, run mutation workflows or broaden scopes.
5. Compare relevant performance page evidence with index state, separating missing rows from zero traffic. Explore chronology/public content changes only with dated evidence. Classify supported technical faults, discovery gaps, content-quality/duplication hypotheses, intentional exclusions and remaining unknowns. Do not invent a causal penalty, sandbox period or ranking cause.
6. If critical details are unavailable, request only useful owner-provided read-only Page indexing/discovery/sitemap-history exports or sanitized Googlebot logs, with no patient data or credential contents. Continue independent public/local investigation while waiting. Lack of OAuth or logs must be documented, not simulated.

## Deliver and validate

Create an ignored `reports/indexing-investigation-<UTC timestamp>/` and matching ignored evidence folder. Include executive-summary.md, url-status-matrix.csv, investigation.md, recommendations.md, proposed-edits.md, evidence-index.md and validation.md.

For each URL, state whether it should be indexed and why; observed state versus diagnosis; supported/ruled-out/unknown hypotheses with confidence; evidence URLs/files/timestamps; urgency and impact/confidence/effort scores (1–5); useful next evidence and measurement. Treat therapy as the first investigation priority but confirm any actual setting/code defect before prescribing a correction.

Any concrete local remedy must show affected URL/setting, exact current/proposed text or code, intended action, factual confirmations, tests, rollback and remaining uncertainty. Draft source only against actual inspected integration; otherwise complete conditional editorial/configuration proposals. Verify report completeness and evidence hashes. Preserve existing audit snapshots and the tracked public baseline; keep account metrics and private detailed findings ignored. A separate sanitized handoff can exclude metrics/account identity/secrets.

Production writes are prohibited, remote staging is deferred, and no website or account changes are approved. Do not edit WordPress/Elementor, trigger autosaves, change settings/canonicals/redirects, delete pages/templates, install plugins, change DNS, submit/delete sitemaps, request indexing, create mass location pages or buy hosting. No external action is implied by an official troubleshooting recommendation. End with evidence-backed conclusions, unresolved causes, exact conditional remedies, completed artifact links and specific owner inputs. Do not dispatch another agent/chat automatically.
