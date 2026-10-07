# Library and skill recommendations

Researched October 7, 2026 against the project's current Python implementation and primary documentation. These are recommendations for the planned app; no packages or skills were installed and no application behavior was changed.

## Recommended architecture

Keep the existing Python engine. Add Streamlit, a local SQLite metadata store, validated configuration and secure credential handling. Model the audit as **base rules + industry profile + site settings**. Use a small explicit rule registry instead of introducing a plugin framework or general rule language.

Start with `general` and `psychology` profiles. The two current sites can use psychology rules with completely independent client facts and evidence. A future electrician, shop or other unrelated site should select `general` until an appropriate industry profile is available. Specific service terms and locations belong in the site's configuration; clinician-review requirements belong in the psychology profile; read-only access, exact approval requirements, evidence integrity and data isolation are enforced across the app.

Profile settings should adjust useful audit behavior: enabled checks, thresholds, priority weights, target-service matching and report wording. They must not override the app's security requirements. Record rule IDs, versions, effective configuration and evidence in each audit so findings remain reproducible.

## Runtime dependencies

| Decision | Library | Reason and intended use |
| --- | --- | --- |
| Add | Streamlit | Local browser interface over the existing Python workflow; forms, data tables and built-in charts are sufficient initially |
| Add | Pydantic | Validate site profiles, industry profiles, permitted overrides, import manifests and report records at boundaries |
| Add | keyring | Access an explicitly verified Windows credential backend for OAuth tokens; store only connection references in SQLite |
| Add | defusedxml | Parse untrusted public sitemap XML with explicit entity/DTD protections, alongside request-size and crawl limits |
| Use standard library | sqlite3, json, pathlib, ipaddress, urllib.parse, unittest | Local storage/configuration, file boundaries, URL/address handling and existing tests without extra services |
| Keep | google-api-python-client, google-auth, google-auth-oauthlib | Existing working read-only GSC integration and Desktop OAuth |
| Keep | requests, Beautiful Soup, pandas, tabulate, tzdata | Existing crawl, HTML extraction, performance analysis, Markdown output and reporting timezone support |

### Pydantic: worthwhile for industry and site configuration

Pydantic supports strict validation and rejecting unexpected fields. Use these intentionally for security-sensitive and rule-override fields, with explicit validators for relationship and semantic checks. Its default type conversion should not silently turn malformed rule settings into accepted values. Sources: [strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) and [extra-field configuration](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.extra).

Validate the profile as a whole after rule resolution: selected industry, known rule IDs, compatible versions, bounded thresholds, allowed override fields, intended URLs, site/audit relationships and phrase groups. Require server-side validation even if the UI restricts the inputs. URL syntax validation is not proof of public network safety, property access or business facts.

JSON is enough for the initial profile files and snapshots; editing through forms removes the need for YAML or a configuration DSL. Keep a schema version for migrations. Pydantic is an implementation recommendation, not a requirement to convert every existing DataFrame or internal object.

### keyring: useful, with an explicit backend check

The project documents Windows support and alternative backends: [keyring documentation](https://keyring.readthedocs.io/en/latest/). Check the backend in the actual Windows environment and reject null/plaintext or unexpected backends. Test storing/loading a non-sensitive probe before migrating a token. Never auto-select another account when retrieval fails.

Treat this as protection for secrets at rest under the OS account, not a guarantee against malware or other code running as that user. Private audit data needs separate protected storage. Verify serialized OAuth credentials fit the actual backend's limits; if they do not, use an OS-protected local token blob with a reviewed storage adapter rather than splitting tokens arbitrarily or falling back to plaintext.

### defusedxml: a targeted crawler improvement

The existing crawler uses `xml.etree.ElementTree` on downloaded sitemap content. Python's documentation warns about XML processing risks for untrusted data and points to defusedxml for server-side parsing: [Python XML security guidance](https://docs.python.org/3/library/xml.html). The library provides compatible parsers with configurable protections: [defusedxml project documentation](https://github.com/tiran/defusedxml).

Use explicit safe parser options and bounded downloads. This addresses XML parsing hazards; it does not solve URL redirects, DNS rebinding, HTML/script rendering or memory consumption from an oversized download. Those controls belong in the shared public-fetch helper and UI rendering layer.

### Keep requests; do not change HTTP libraries just for security

The existing collector already uses requests. Moving to an async HTTP client would add migration work without inherently solving destination validation. Build one reviewed helper used by robots, sitemaps and pages, with explicit redirect checks, hostname boundaries, public IPv4/IPv6 validation, connection-time destination checks, TLS verification, timeouts and bounded responses. Follow [OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

Do not pass Google OAuth headers to the crawler. Test the helper's boundaries offline with controlled fixtures, including redirect and DNS-change cases. Standard-library address classification is one component of the control, not its entirety.

## Testing and dependency security

Use the existing `unittest` suite for the engine and add Streamlit's **AppTest** for simulated UI interactions. It supports manipulating widgets and session state without browser automation: [Streamlit testing documentation](https://docs.streamlit.io/develop/concepts/app-testing). Test switching sites, profile overrides, stale cached recommendations and duplicate launches; complement simulation with a real browser smoke check and socket/storage verification before release. No pytest migration is needed initially.

Add two development tools:

- **pip-tools:** generate pinned dependency files with hashes from a small input list. Compile for the supported Windows/Python environment and keep runtime and development dependencies separate. Its documentation describes hash generation: [pip-tools](https://pip-tools.readthedocs.io/en/latest/).
- **pip-audit:** check the locked dependencies and installed runtime for known vulnerabilities before release and after dependency changes. Review and test fixes instead of using automatic `--fix` during normal app operation. It audits dependencies, not the app's code, and does not detect every malicious package: [PyPA documentation and security model](https://github.com/pypa/pip-audit#security-model).

The current `requirements.txt` uses minimum versions without an upper resolution lock. Preserve the existing working environment while preparing a tested lock for the app; avoid upgrading the full dependency set just to add the interface. Exact versions should be selected during implementation, checked for advisories and validated on the actual Windows/Python environment.

No package makes the app secure on its own. Security acceptance includes scoped database access, cache/file boundaries, credential handling, safe fetching, source-aware imports, storage protection and read-only external behavior.

## Skills: use a small project-specific audit workflow

Agent skills provide reusable instructions and supporting references for repeatable work; they are not a substitute for enforced application controls. Official documentation describes their structure and repository discovery: [Build skills](https://learn.chatgpt.com/docs/build-skills).

Recommend a single repo-scoped `seo-audit` skill once the profile format and runner exist. Use the already available **skill-creator** to author it. Its job should be to:

- Select an explicit site and audit, then load that site's profile and effective industry rules.
- Follow the evidence sources and metric definitions, including missing-data and sample-size limits.
- Generate the site's executive summary, recommendations and locally proposed edits with source references.
- Load psychology guidance only for sites selecting that industry profile, and use only that site's confirmed clinical facts.
- Reuse shared lessons only when their industry/service applicability and evidence requirements are met.
- Preserve website approval and read-only GSC boundaries; neither skill invocation nor a shared lesson grants publication permission.

Keep the shared workflow in `SKILL.md`, with concise industry references loaded only when relevant. Private site facts and evidence stay outside the shared skill. App-validated configuration remains the source of truth for enabled rules and profiles; do not maintain a second contradictory rule system in agent prose.

A reviewed shared-lesson promotion procedure can be a mode in this skill later, rather than another learning subsystem. Do not install a generic SEO skill that brings its own unchecked assumptions about keyword density, automated publishing, page creation or rankings. Any externally sourced skill should be inspected for relevance and permissions before installation.

The existing **OpenAI Docs** skill is useful for official documentation when adding agent/AI features. The current documents, spreadsheet and PDF skills are useful only if later deliverables require those formats; ordinary Markdown/CSV outputs do not justify loading them. Browser-control skills may support a specific read-only rendered-page investigation, but the normal audit should keep using the existing collector.

Before release, perform an explicit security review of this app's credential, site-isolation and crawler boundaries. A dedicated security-review skill could support that if later selected and available; it would supplement code review and tests. No dedicated security-review skill is exposed in this session, and this research does not install one or claim a security audit has been performed.

## Defer until a concrete need appears

- SQLAlchemy/Alembic: useful for a larger database model or deployment, but unnecessary for six small SQLite tables and explicit migrations.
- Pluggy, Drools-style engines or executable third-party audit plugins: unnecessary for a small trusted rule registry; imported client files should never execute code.
- LangChain, vector databases and cross-client retrieval: unnecessary for transparent rule-based recommendations and scoped evidence packets.
- Playwright/Scrapy: consider when a real site needs JavaScript rendering or the crawl scale outgrows the current collector.
- GA4, Business Profile or paid ranking/backlink integrations: add only when their measurements are needed and their separate access is deliberately configured.
- Authentication add-ons, public hosting and client portals: separate scope after the local single-user version is useful.
- Custom encryption libraries or a homegrown credential vault: prefer OS-managed protection and reviewed backup handling for this Windows MVP.

The implementation priority remains secure per-site operation, explicit industry applicability, and useful recommendations for Meadow & Mind and the second psychology site. Broader industry coverage should require adding a reviewed profile, not rewriting the engine or inheriting another client's concerns.
