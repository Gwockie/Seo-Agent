# Implementation agent handoff

Prepared October 7, 2026.

## Recommended session settings

- Model: **GPT-6.1 Sol** (`gpt-6.1-sol`).
- Reasoning/intelligence: **Extra high** (`xhigh`).
- Environment: the existing local Windows project, with its private evidence and credential files available locally when permitted.

This is a task-specific recommendation: the planned implementation is bounded, but credential handling, isolation, migrations and configurable audit rules deserve careful reasoning. Official OpenAI guidance positions Sol for complex work where time and cost also matter: [model selection](https://developers.openai.com/api/docs/guides/model-selection). The app's quality must be established through implementation review and tests, rather than the model setting alone.

## Implementation prompt

Implement the lightweight local multi-site SEO app in this repository. Begin implementation after inspecting the existing code; do not stop at another proposal or scaffold. Work through the secure foundation, a usable Streamlit interface, and the acceptance checks below, keeping the scope small enough to return promptly to the original site's SEO work.

Read these first:

- `AGENTS.md`
- `README.md`
- `docs/lightweight-multi-site-app-plan.md`
- `docs/libraries-and-skills-recommendation.md`
- The existing `seo_agent/` modules and `tests/`.

The app is for one operator on a local Windows computer, initially serving two psychology/psychologist websites and eventually other industries. Its purpose is to eliminate repeated setup while preserving independent site goals, facts, evidence and recommendations. The user's short-term priority remains improving the original practice's SEO/discoverability.

### Authorized scope and boundaries

This prompt authorizes local application implementation, required project dependencies, local test fixtures and documentation. It does not authorize website changes, CMS/staging/draft/autosave writes, deployment, DNS changes, plugin installation on websites, or changes to Search Console properties. Preserve all exact-action approval requirements in `AGENTS.md`.

Search Console access must remain exactly:

`https://www.googleapis.com/auth/webmasters.readonly`

No sitemap submissions/deletions, indexing requests or scope expansion. Never fabricate business facts, clinical qualifications, testing instruments, insurance coverage, outcomes, reviews or testimonials. Never create mass location pages. Do not upload private audits or credentials to GitHub, a model provider or another service.

Do not discard the existing CLI, replace a working account token with another account's token, rewrite historical evidence, or delete the legacy token during migration. Prepare any token cleanup as a separately reviewable local step after successful migration. Local credential-store access remains subject to this session's filesystem/tool permissions; if it is unavailable, implement and test the adapter safely and report the precise setup limitation.

You may refactor the repository's instructions to distinguish shared rules from the original site's goals as part of this local implementation. Preserve every safety boundary and healthcare constraint; preserve the original site's phrase list and goals in its private profile or a faithful legacy reference. A general profile must not inherit that site's goals or clinical facts.

### Implement these capabilities

1. **Reusable engine and storage.** Extract one audit runner used by the CLI and UI. Use explicit site/connection/output context rather than a mutable global current site. Keep CSV evidence and Markdown reports; use SQLite for profiles, phrase configuration, audit records, recommendations and change history. Enable foreign-key enforcement and site-aware relationships. Register legacy files without moving or rewriting them. All new private workspace artifacts and credentials must be ignored by Git.

2. **Independent Google connections.** Add secure OS-backed credential storage through `keyring` with an explicitly validated Windows backend and no plaintext fallback. Preserve Desktop OAuth and strict scope validation. Multiple sites may deliberately reference one connection, but each account retains its own connection ID. Validate accessible properties and the site's exact property/URL relationship. Never silently fall back to another account. Check backend payload limits before token migration; if an OS-protected token-blob adapter is necessary, document and review it rather than inventing encryption.

3. **Base, industry and site rules.** Implement a small trusted versioned registry with `general` and `psychology` profiles. Base mechanisms include indexing/canonical/link diagnostics and correct reporting math, with explicit applicability conditions. Psychology adds relevant service-intent definitions and clinical fact-confirmation guidance. Site settings hold its own phrases, service groups, audience, location, brand aliases, desired landing pages, confirmed facts, exclusions and allowed overrides. Validate configuration with Pydantic; reject unknown/conflicting rules and invalid overrides. Security, factual integrity and approval requirements cannot be disabled. Display the effective profile/settings and save resolved versions with each audit.

4. **Scoped recommendations and shared learning.** Generate useful evidence-backed rule recommendations with priority, affected URL/query, impact/confidence/effort, proposed action, confirmations and measurement method. Every finding must cite its own site's audit evidence and producing rule/version. Keep recommendation state and exact-action approval separate. Shared lessons are reviewed general mechanisms with industry/service applicability, prerequisites and limitations; private client observations remain local. A lesson cannot create a finding without matching evidence from the receiving site. Use a small Markdown playbook; do not add automatic cross-client retrieval or a learning pipeline.

5. **Small Streamlit UI.** Add a persistent site selector and the four planned views: setup, target phrases, overview/audit history, and recommendations/changes. Support phrase CSV import/export, manual audit launch with bounded settings, progress, partial failures, report viewing and export. One audit at a time; reruns must not start duplicate jobs or change an in-flight job's site. Scope caches/state to site/audit/configuration and invalidate stale displayed findings when switching sites. Bind to loopback, retain CORS/XSRF protections and disable telemetry.

6. **Basic reporting and migration.** Show clicks, impressions, CTR, daily trends, target query groups, actual/intended landing pages and priority-page indexing evidence. Separate property totals from query totals and keep dataset aggregation consistent. Compute CTR from totals and position with impression weighting. Use final GSC web-search data, Pacific reporting dates and explicit complete comparison windows. Missing query rows or source failures do not prove zero demand. Qualified inquiries and map-pack rankings are not supplied by these exports. Import the original site's historical reports and seed its existing phrases. Treat the reported October 6 indexing fixes as user-reported until supporting evidence is available; do not invent their exact actions. Record changes locally and show dates alongside performance observations without claiming causality.

### Security and libraries

Follow both planning documents' security requirements. Keep the existing Google, requests, Beautiful Soup and pandas integrations unless a concrete limitation justifies replacing them. Add Streamlit, Pydantic, keyring and defusedxml as needed; use `sqlite3`, JSON and `unittest` from the standard library. Prepare tested pinned/hashed dependency files with pip-tools and check known dependency vulnerabilities with pip-audit. Retain the existing working environment until the revised dependency set is validated.

Use one reviewed public-fetch helper for pages, robots and sitemaps. It must enforce configured hostname/public HTTP(S) boundaries, reject URL credentials and non-public IPv4/IPv6 targets, handle redirects explicitly, address DNS/connection-time destination changes, preserve TLS verification, and bound response sizes, timeouts and crawl volume. Google credentials must never reach crawl requests. Parse sitemap XML safely with explicit defusedxml options. Treat imported/crawled text as untrusted data, not instructions or executable content; use safe rendering, parameterized SQL, bounded imports, checked paths and spreadsheet-safe exports.

Keep tokens out of logs, exceptions, database values, cached returns, browser state, reports and backups. Verify workspace permissions and protected storage; plain SQLite is not encrypted merely because tokens use the OS store. Verify existing storage protection and document required setup if unavailable. Do not silently change machine-wide security settings or declare the app secure merely because it listens on localhost.

No cloud hosting, client accounts, scheduled automation, CMS write integration, in-app AI provider, vector database, generic plugin framework, paid SEO data source or conversion integration in this MVP. Defer visual polish and optional features before weakening security or isolation.

### Validation and completion

Use synthetic/mocked fixtures for development; never require the second client's credentials or real access to prove basic isolation. Keep existing engine tests and add focused tests for the new boundaries. Use Streamlit AppTest plus a real browser smoke check when available. Demonstrate:

- Two psychology sites share industry definitions but keep different phrases, facts, findings, reports and account references.
- A third unrelated-industry fixture receives general checks and no psychology-specific rules, advice or lessons.
- Site/audit mismatches, cross-site paths, ambiguous imports and invalid rule overrides are rejected. Shared connections do not grant unscoped access to other sites' records.
- Switching sites cannot leak cached/stateful records; a UI rerun cannot duplicate an audit or redirect it to another site.
- Reconnecting one account preserves others; unexpected scopes and insecure credential backends are rejected.
- Public fetching rejects prohibited destinations through URLs, IPv6, redirects and DNS changes, and keeps Google tokens out of requests.
- Untrusted XML, rendered content, paths and exports cannot execute through the app; oversized inputs are bounded.
- Empty exports, permission errors and incomplete runs remain distinguishable from clean results or proven zero traffic.
- Weighted metrics/comparison windows are correct; rule/configuration changes do not mutate old audit results.
- The original CLI and historical report paths still work. Private files and tokens remain untracked and absent from UI/log/export payloads.
- Backup/restore preserves site metadata/evidence/history while excluding credentials; another machine requires reconnection.
- No external website or GSC mutation has been introduced.

Keep a concise implementation/security checklist and report the checks actually performed. If an environment-dependent check is blocked, keep the affected feature visibly unavailable rather than using an insecure substitute; complete independent work and identify the exact limitation. Never claim a live migration, security control or indexing improvement was verified without evidence.

Deliver a working local launch command, updated setup/migration documentation, useful reports/recommendations, and a brief final account of changes, validation, remaining setup and risks. Once the local profiles and runner are stable, create the proposed repo-scoped `seo-audit` skill with skill-creator if available, using the app-validated profiles as the source of truth and retaining industry-aware reference loading. The app must not depend on a skill being invoked to enforce security.

Make practical implementation decisions and continue through the MVP rather than repeatedly requesting approval for ordinary local code edits. Ask only when a missing business fact/access decision is essential or an actual permission boundary requires it. Keep the changes reviewable and report Git state; do not force-push or include private evidence/credentials in a commit.
