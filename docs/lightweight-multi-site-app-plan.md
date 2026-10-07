# Lightweight multi-site SEO app plan

Prepared October 7, 2026. This is a local implementation plan, not authorization to change any website or Search Console property.

## Recommendation

Build a small, local, single-user SEO workspace around the existing Python audit engine. Open it in a browser on this Windows computer, choose a site, run an audit, review recommendations, and compare results. Keep the current command-line workflow working.

The first release should solve repeated setup and lost context: account connections, site goals, target phrases, evidence, recommendations, and change history. It should be useful for Meadow & Mind and one additional site before we consider a larger product.

Assumptions: you operate the app; clients do not log in; a handful of sites; manual audit runs; public website content and authorized Search Console data. Cloud access and multiple operators would require a separate design decision.

Confirmed direction: Streamlit is acceptable. Security and separation between sites are foundational requirements. Reusable mechanisms and reviewed general lessons should improve the shared engine, while each site's findings, private context and recommendations remain separate.

Industry differences are explicit: the two current sites can select the same psychology profile, but a new site's industry must be configured independently. Library and skill choices are documented in [the research recommendation](libraries-and-skills-recommendation.md).

## What already exists

| Existing component | Keep | Small change needed |
| --- | --- | --- |
| `seo_agent/gsc.py` | Performance exports, property listing, sitemap metadata, read-only URL Inspection | Resolve the site's chosen Google connection; support explicit comparison windows |
| `seo_agent/crawl.py` | Public HTTP crawl, robots checks, host boundaries, technical page evidence | Replace ADHD/Paoli-specific content flags with configurable service/location checks |
| `seo_agent/analysis.py` | Query/page analysis and mechanical Markdown summaries | Replace hardcoded target patterns; add brand separation, rule-based findings, and site-specific report context |
| `seo_agent/auth.py` | Desktop OAuth and exact read-only scope validation | Replace the single token file with an account-aware credential store |
| `seo_agent/__main__.py` | Existing CLI entry point | Extract the audit orchestration into a shared function used by the CLI and UI |
| `data/` and `reports/` | CSVs, manifests, evidence and readable reports | Register existing runs and isolate future runs by site |

Today, changing accounts replaces `secrets/token.json`. Snapshots share timestamp-only folders, and the engine treats ADHD, therapy, psychological testing, and Paoli as universal targets. Those are the main barriers to reuse. The current opportunity score is a heuristic; the app should not present it as a reliable prediction of SEO impact.

The October 5 Meadow & Mind snapshot is a historical baseline. You report indexing fixes on October 6; the inspected local baseline does not verify their current effect. Import the old audit with its original dates, record the fixes as user-reported changes, and collect a fresh read-only inspection when SEO work resumes.

## The first release

Use a persistent site selector and four simple views:

| View | What you can do |
| --- | --- |
| Site setup | Save website URL, exact Search Console property, account connection, business/location context, brand terms and confirmed business facts |
| Target phrases | Save phrases, related service terms, location intent, priority and intended landing page; import/export CSV |
| Overview & audits | Run a bounded audit, see progress and source failures, open old audits, inspect performance and indexing evidence |
| Recommendations & changes | Review evidence-backed recommendations, edit local drafts, record decisions and externally implemented changes, export a report |

### Site profiles and phrases

Store a business name, final public hostname, exact GSC property identifier, primary location/service area, brand aliases, priority services, and notes. A GSC URL-prefix property and a domain property are distinct; never silently swap them during reporting.

Each target phrase has an exact phrase, intent/service group, optional location, priority, preferred landing page, and active flag. Use simple editable lists of related terms rather than requiring users to write regular expressions. Track exact matches separately from related query groups and deduplicate queries that match several phrases.

For Meadow & Mind, seed the ten phrases already listed in `AGENTS.md`. Keep ADHD assessment/testing/evaluation together as related intent while retaining exact-phrase reporting. Treat "near me" as local intent rather than prompting literal repetition in website copy. A second site's services, geography, brand aliases and facts must be entered independently.

Save a version of the profile and phrase configuration with each audit so that later edits do not silently redefine historical results.

### Account connections and credentials

Store OAuth tokens in the Windows credential store through Python `keyring`, with only connection IDs and display labels in the app database. Its documentation lists a supported Windows backend: [keyring documentation](https://keyring.readthedocs.io/en/latest/).

One Google connection can serve several authorized properties. Different accounts get different connection IDs; reconnecting one must preserve the others. An account hint is not proof of the selected identity: display the accessible properties and require an explicit property selection for the site.

Preserve the existing Desktop OAuth flow and exactly this scope:

`https://www.googleapis.com/auth/webmasters.readonly`

Validate scopes on load and after authorization. Validate property access and the property's relationship to the public URL before starting an audit. If the secure Windows backend is unavailable, show a connection setup error rather than falling back to plaintext storage.

Keep downloaded OAuth client configuration out of Git and exports. Tokens must never appear in the UI, reports, logs, database or backups. Preserve the existing token file until its migration has been tested successfully; local removal is a separate explicit migration step. App backup restoration on another computer should require reconnecting Google.

For v1, credentials means Google connections needed for auditing. Website administration credentials are unnecessary for this app's read-only workflow; keep those in the existing password manager. A later integration should use a separate, deliberately approved design.

### Recommendations

Make **basic recommendation generation part of v1**, using transparent rules and report templates. Examples:

- A configured priority page has an observed indexing restriction or a conflicting Google canonical: report the exact evidence and a specific next diagnostic or proposed remedy.
- A target query's observed landing page differs from the intended service page: flag the mismatch, with query/page metrics and sample dates.
- A priority page has a verified broken internal destination: identify the source URL, destination and suggested repair.
- A service page lacks configured service/location language: suggest factual content review, with the exact title/headings and configured terms that triggered the finding.
- A page has impressions and weak CTR: suggest reviewing the search snippet; show the sample size and avoid treating one arbitrary CTR threshold as proof of poor copy.

Every item stores: priority P0–P3, category, affected URLs/queries, evidence file/rows, impact/confidence/effort 1–5, proposed action, factual confirmations, measurement method, and status. Low-data or ambiguous findings should be labeled as diagnostic leads rather than certain causes. Several pages appearing for a query is a review signal, not automatic evidence of harmful cannibalization.

Use `proposed -> reviewed -> implemented -> verified`, plus `dismissed`. Record factual confirmation and exact-action approval separately; reviewing a recommendation does not authorize a website change. Imported narrative reports can retain human judgment without pretending it came from automated rules.

Generate the existing three report types from the selected site's goals: executive summary, recommendations, and proposed edits. An unrelated business's summary should discuss its own target services, rather than asking whether Google understands ADHD assessment.

For deeper interpretation or complete replacement copy, continue the current human/agent review workflow: export a site-specific evidence packet and import the reviewed reports. This avoids adding an LLM integration to the first build. An optional in-app AI provider can follow later; it should receive only the chosen site's scoped evidence, return drafts with evidence references, and retain provider/model/template provenance. No credentials or unrelated clients' data belong in that payload.

### Separate site knowledge and shared mechanisms

Use two explicit layers, rather than one pooled history of recommendations:

| Layer | Contents | Reuse policy |
| --- | --- | --- |
| Site workspace | Credentials references, business facts, phrases, URLs, raw evidence, findings, recommendations, approvals, changes and observed outcomes | Available only in that site's selected context |
| Shared engine and playbook | Audit rules, technical diagnostics, report structure, reviewed general lessons, applicability conditions and limitations | Can be evaluated for any site, but must produce a fresh finding from that site's own evidence |

Resolve audit rules through three explicit levels:

1. **Base rules:** industry-independent mechanisms such as fetch/indexing diagnostics, canonical consistency, broken links, query/page alignment and reporting math. Each still has applicability conditions; deliberate exclusions such as a noindex utility page are not automatically defects.
2. **Industry profiles:** versioned groups of rules, terminology, fact-confirmation requirements and report sections. Start with `general` and `psychology`. The psychology profile contains clinical-content review requirements and service-intent definitions; it contains no client's confirmed clinical facts, locations or credentials.
3. **Site configuration:** target services, phrases, brand aliases, audience, geography, intended pages, intentional exclusions, business facts and permitted rule settings. Sites can adjust thresholds, priorities and enabled audit checks within validated limits. They cannot disable credential scope restrictions, site isolation, untrusted-content handling, factual integrity or external-write approval requirements.

Both current sites may choose `psychology`, with independent services and clinician-confirmed facts. An unrelated business starts with `general` until a suitable industry profile is deliberately selected. Do not infer a clinical profile merely because another site's most recent audit used it.

Use stable rule IDs and explicit override fields rather than arbitrary dictionary merges. Reject unknown rules, incompatible profile versions and conflicting definitions. The UI should show the effective profile, rule source and site overrides. Save the fully resolved rule configuration and versions with every audit; changes affect future runs, not historical findings.

Shared lessons carry an applicability scope (`general`, a named industry, or a specific service/business context), required evidence and exceptions. A psychology-only lesson must be excluded from unrelated industries before evidence or generation context is assembled. Shared technical mechanisms can be used across industries; recommendation language, priority and confirmation requirements come from the active profile and site configuration.

For example, a broken internal link discovered on Meadow & Mind can improve a general rule that detects links to an unexpected final destination. Another site's recommendation must identify its own source anchor, intended destination and observed redirect chain. Meadow & Mind's URLs or replacement copy must never become the other site's recommendation.

Similarly, an observed improvement after a title change may suggest a reusable hypothesis about clearer service/location language. It does not prove that the title caused the improvement or that every site needs that edit. Each application must consider the current site's audience, facts, intent and evidence.

Implement the shared layer initially as a small versioned rule catalog and a reviewed Markdown playbook. No vector database, cross-client retrieval system or automated learning pipeline is needed for v1. Rules should be trusted application code or declarative configuration; imported lessons must not execute code.

Each shared rule records an ID/version, applicability scope, diagnostic mechanism, required evidence, applicability conditions, exceptions, overridable settings, recommendation template and validation method. Each site finding records the producing rule/version, site ID, audit ID, exact source evidence and industry/site profile versions. Store the proposed action locally for that site; never load another site's recommendations as generation context.

New general lessons follow a deliberate process:

1. Keep the observation and outcome in the originating site's private change history.
2. Prepare a generalized lesson describing the mechanism, prerequisites, limits and strength of evidence. Remove names, domains, credentials, business/clinical facts, private query examples, metrics and copied client content.
3. Review it before adding it to the shared playbook. Mark uncertain lessons as hypotheses, and distinguish technical verification from search-performance observations.
4. Evaluate its applicability against another site's own evidence before generating a recommendation. Missing evidence should lead to a diagnostic question, not an inherited conclusion.

General software fixes and tested audit mechanisms can improve the engine for every site. Outcome-derived lessons require review before promotion. Preserve rule versions so a later engine improvement does not rewrite historical reports; label newly regenerated analysis as a new version.

Keep healthcare factual constraints applicable to health-related sites. Clinician-confirmed facts, publication approvals, dismissal decisions and evidence of success remain site-specific. A shared mechanism carries no permission to implement it on another website.

### Reporting and change history

Show property clicks, impressions, CTR, daily trends, target non-branded query groups, actual versus intended landing pages, and priority-page indexing status. Keep property totals separate from query-derived totals.

Use Search Console dates in Pacific time, final web-search data, and the existing default three-day lag. Start with equal adjacent 28-day windows, with 90-day views available for context. Fetch enough daily/query/page data for both windows; the current 90-day export alone cannot supply a preceding 90-day comparison.

Calculate CTR as total clicks divided by total impressions; calculate aggregate position with impression weighting within the same dataset and aggregation. Never average row CTRs or row positions without weighting. Represent absent or unavailable data as unavailable, rather than a proven zero.

Google documents that the API returns top rows and does not guarantee all rows: [Search Analytics query reference](https://developers.google.com/webmaster-tools/v1/searchanalytics/query). Show query omissions and export limits alongside results. Brand classification is an editable approximation based on visible queries. Search Console average position is not a fixed local ranking or a map-pack ranking. Qualified inquiries require additional measurement; v1 should allow notes or manual counts without claiming attribution to organic search.

The change log stores date, affected URLs, exact action, prior/proposed values when available, approval reference, implementation evidence, and verification status. Put change dates on the performance chart. Website changes can be recorded locally after separate implementation; the app itself has no publishing control. Before/after comparisons are observations, not proof that an edit caused a change.

## Lightweight technical design

Use **Streamlit + SQLite + the existing Python modules**. Streamlit is the recommended tradeoff for a small internal Python dashboard; SQLite keeps metadata in a local file without another database service. Python includes a SQLite interface: [Python documentation](https://docs.python.org/3/library/sqlite3.html).

Bind the app explicitly to `127.0.0.1`, retain its normal request protections, and disable usage telemetry. Streamlit exposes these settings through [its configuration file](https://docs.streamlit.io/develop/api-reference/configuration/config.toml). A local launcher can open the browser. No hosted app, client accounts or separate JavaScript frontend is needed for this release.

Conceptual storage:

```text
workspace/
  app.sqlite
  sites/<site-id>/
    audits/<audit-id>/
      manifest.json
      data/       # CSV exports and captured public evidence
      reports/    # Markdown and generated local drafts
```

Credentials live in the OS store, outside this tree. Ignore the entire private workspace, database files, and generated artifacts in Git. Export reports deliberately; backups contain private audit data and must exclude credentials. Use generated IDs, not user-entered path components.

Small database tables: sites, connections (references only), target_phrases, audits, recommendations, and change_events. Foreign keys associate every site-specific record with its site; connections can be shared deliberately. Enable foreign-key enforcement on every SQLite connection and use site-aware relationships so a recommendation for site A cannot reference an audit for site B. SQLite documents explicit enforcement configuration in [its foreign-key reference](https://www.sqlite.org/foreignkeys.html). Keep bulk performance data in CSVs for now. Use a schema version and simple migrations, not an ORM or a large database abstraction.

Extract `run_snapshot(...)` from the CLI into a reusable orchestration module. Pass an explicit site configuration, connection and output directory; avoid mutable global "current site" state. The UI and CLI must call the same engine. Scope cached data to site ID, audit ID and configuration version. Invalidate displayed recommendations when switching sites.

Start with one audit at a time, an explicit Run button, progress callbacks and a run lock. Streamlit reruns must not duplicate a job. Record per-stage success/failure, timestamps, API data windows and warnings in the manifest; mark incomplete runs visibly and preserve completed stages for diagnosis. Disable repeated launch while running. No distributed workers or background scheduling in v1.

Keep the collector CMS-independent; crawling a WordPress site is only one use case. Separate the general read-only safety policy from site-specific goals when implementation begins. Preserve the healthcare fact-confirmation rules in the Meadow & Mind profile, and never inherit its clinical facts into another site.

## Security requirements for v1

Security is part of the foundation, not a later UI enhancement. The acceptance criteria below describe controls to implement and verify; this plan does not claim the current tool already satisfies them.

- **Local access:** bind only to loopback, retain CORS/XSRF protections, and keep telemetry disabled. Do not expose the app through a tunnel or public hosting. A shared Windows session or compromised user account is outside this app's isolation boundary; loopback is not user authentication. Remote or multi-user use requires authentication and authorization before deployment.
- **Credential handling:** use the verified secure OS backend, retain the exact read-only GSC scope, never put tokens into Streamlit cached return values or browser session state, redact exception details, and separate API credentials from public crawl requests. A disconnected or invalid connection must not silently use another account.
- **Site isolation:** require site ID in repository/service methods, enforce site-aware database relationships and path boundaries, and key caches by the full site/audit/configuration context. Check report imports against the selected site's manifest; ambiguous legacy imports require explicit association. A site selector alone is insufficient protection. Reports and exports must include only the selected site's records.
- **Crawler boundaries:** allow only public HTTP(S) targets on the configured hostname. Reject URL credentials and non-public IPv4/IPv6 destinations, including loopback, private and link-local addresses. Validate DNS resolution and the actual destination at connection time, and handle redirects explicitly through the same checks for robots, sitemaps and pages. Retain TLS verification, timeouts, response-size limits and crawl limits. This design should follow [OWASP's SSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
- **Untrusted content:** treat crawled pages, imported reports and query text as data. Never execute page scripts, imported Python, SQL fragments or instructions found in content. Render through safe components; do not enable unsafe HTML for fetched text. Use parameterized SQL, bounded input sizes and generated file IDs. Produce spreadsheet-safe CSV exports without altering preserved raw evidence.
- **Local files and backups:** restrict private workspace access to the operating Windows account; verify the chosen path's permissions. Audit data and ordinary SQLite files are not encrypted merely because tokens use the OS store. Require protected storage and encrypted backups for private data; verify existing disk encryption or choose OS-managed encryption rather than inventing a crypto scheme. Backups exclude tokens and OAuth client configuration. No patient records belong in this app.
- **Dependencies and failures:** lock tested dependency versions, check vulnerabilities before release, and sanitize user-facing errors and stored error records. Fail closed on missing scope, property access, destination validation or credential-store support. Preserve partial audit evidence without representing a failed stage as a clean result.

Include a lightweight security review and the isolation checks below before using the app for a second client's data. Hosting, client access and future AI providers each need a review of their changed data boundaries.

## Build sequence and stopping point

These are rough hands-on engineering estimates, not promises; OAuth migration and report comparison may increase them.

| Step | Scope | Estimated effort | Done when |
| --- | --- | --- | --- |
| 1. Reusable foundation | Site profiles, base/industry/site rule resolution, versioned shared playbook, configurable query/crawl rules, scoped folders, shared runner, independent secure Google connections and security controls | 1–2 focused days | Two site configurations can be selected and audited without replacing accounts or mixing evidence; security/isolation checks pass |
| 2. Small app | Four views, keyword editor, audit progress/history, rule-based recommendations, basic charts, Markdown/CSV export | 1–2 focused days | Routine setup, audit and review work from the browser |
| 3. Preserve and measure | Register old Meadow & Mind reports, record yesterday's fixes, compare equal windows, change log and backup/restore | About 1 focused day | Historical evidence remains intact and follow-up reporting is usable |
| Later, only when needed | Optional in-app AI drafting, scheduled runs, conversion integration, richer local/competitive evidence, hosting or client access | Separate scope | Repeated actual use demonstrates the need |

Target a **3–5 focused-day MVP**, with an early usable checkpoint after step 1. Security and isolation are release requirements; if they increase effort, defer interface polish and optional reporting features rather than weakening them. If the app work grows beyond that budget, stop at the working foundation and use the CLI while returning to Meadow & Mind's optimization. Adding a second site must not depend on finishing a polished dashboard.

## Migration and validation

1. Register Meadow & Mind with its existing URL-prefix property, phrase list and healthcare constraints. Leave historical files in their current locations and reference them through imported audit records; do not rewrite them.
2. Explicitly associate the existing Google token with a connection, copy it to the secure store, validate scope/property access, and verify the original CLI still works.
3. Import the October 5 live audit as the baseline. Label the public-only audit separately so missing GSC data cannot be mistaken for zero performance.
4. Enter the October 6 changes with their actual details when available. Keep them marked user-reported until evidence confirms implementation and indexing status.
5. Create an unrelated second-site fixture with different phrases and account references. Validate isolation offline; use a live second-client audit only when authorized access is available.
6. Resume SEO work with a fresh read-only inspection of the affected priority pages, then use subsequent completed reporting windows to assess discoverability.

Acceptance checks should focus on real failure modes:

- Switching sites never exposes another site's keywords, reports, cached metrics or recommendations.
- A mismatched site/audit ID is rejected by service methods and database constraints, including for exports and imported reports.
- The same general rule generates independent findings for two sites using only their own evidence. A rule that lacks evidence for site B cannot copy site A's finding.
- Two psychology sites share rule definitions but retain different facts, phrases, priorities and findings. A third, unrelated-industry fixture never receives psychology-specific checks, language or lessons.
- Valid site overrides change only that site's audit settings. Unknown/conflicting rule definitions are rejected, and security/factual-integrity requirements cannot be disabled by a profile.
- Shared lessons contain no private site identifiers/content, and historical reports retain the rule versions that produced them.
- Reauthorizing one connection preserves other connections; unexpected scopes are rejected.
- Crawl requests cannot reach non-public addresses through direct URLs, IPv6, redirects or DNS changes; robots/sitemap fetches use the same checks. Crawl sessions never receive Google tokens.
- Untrusted HTML, paths and CSV formulas cannot execute through report display, import or export; oversized responses are bounded.
- The app listens only on loopback; private file permissions and storage/backup protection are verified, and tokens cannot be found in captured logs, UI payloads, exports or cache contents.
- Configurable classification works for an unrelated service/location without ADHD or Paoli leaking into its findings.
- Existing CLI commands and historical report paths remain usable.
- Empty exports, permission failures and partial audits display clear source status.
- Known fixtures produce correct weighted metrics and distinguish missing observations from zero.
- A UI rerun cannot launch the same audit twice.
- Report generation cites the source audit and excludes tokens; backup/restore preserves profiles/history and requires reconnection on another computer.
- No app code mutates websites, submits sitemaps, requests indexing, changes GSC properties or broadens OAuth scopes.

The MVP is finished when you can add a second site without editing Python, keep both sets of credentials and goals, run separate audits, review useful recommendations, and revisit Meadow & Mind's baseline and changes. At that point, return to the website's high-value SEO work and let repeated use determine the next app feature.
