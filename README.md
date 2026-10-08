# Local multi-site SEO workspace

A small Windows/Streamlit app around the existing read-only Python SEO auditor.
Select an independent site, configure its goals and Google account reference, run
an audit, review evidence-backed recommendations and save local proposed edits.
The original CLI and historical data/report paths remain available.

Website changes require explicit human approval of exact actions under
[AGENTS.md](AGENTS.md). The app has no CMS write integration. Search Console uses
only `https://www.googleapis.com/auth/webmasters.readonly`.

## Launch

Validated for Windows and Python 3.13. Keep any existing environment until the new
one has passed your checks:

```powershell
py -3.13 -m venv .venv-mvp
.\.venv-mvp\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-mvp\Scripts\python.exe -m seo_agent app
```

Open [the local app](http://127.0.0.1:8501). To try the views immediately with
three synthetic sites and no credentials/network collection:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent app --demo
```

After local setup is complete, you can also double-click **Start SEO App.cmd** in
this folder. Keep its window open while using the app. See
[reviewing together in the app](docs/review-in-app.md) for the review workflow.
Setup has help tooltips and editable lists; recommendations explain expected
effects and support a local **Changes & results** journal. See
[guided setup and learning](docs/guided-setup-and-learning.md).

The next agreed [change-to-results workflow](docs/seo-change-workflow.md) has
separate copyable prompts for [building tracking](docs/change-tracking-agent-prompt.md)
and [continuing Meadow & Mind's audit](docs/meadow-and-mind-agent-prompt.md) in parallel.

Demo data lives separately in `workspace/demo`. Real data defaults to
`workspace/private`; all private files, SQLite databases, raw evidence, credentials
and reports are ignored by Git. No audits or credentials are bundled.

## Before real client data

Read [setup and migration](docs/setup-and-migration.md). Private writes, live
collection, credential setup/migration and local backup require verified Windows
folder access restricted to your account, SYSTEM and Administrators. Disk
encryption is optional under the [approved local policy](docs/local-storage-policy.md).
An unavailable access check fails closed. SQLite itself is not encrypted. The
launcher uses loopback, CORS/XSRF protections and disabled telemetry; this is a
single-user tool.

Google tokens use exactly the validated Windows WinVaultKeyring backend, with no
plaintext fallback. Each connection has its own generated ID; reconnecting one
preserves others. The 2,560-byte UTF-16 backend limit is checked before writes.
Legacy token migration copies and validates, never deletes or rewrites the original.

## Workflow

- **Setup:** independent business/location/audience, brand aliases, confirmed facts,
  service groups, exclusions, exact GSC property and connection. Review effective
  base + industry + site rules. Select psychology deliberately; new sites default
  to general. Saved URL/property identities cannot be changed to a different site.
- **Target phrases:** exact targets, related intent terms, priority and intended
  pages; bounded, explicitly site-associated CSV import/export.
- **Overview & audits:** bounded manual collection, progress, source failures,
  history, property metrics, daily trends, query groups, landing pages, inspection,
  equal complete comparison windows and safely formatted report viewing/export.
- **Recommendations & changes:** rule/version and own-site CSV row evidence,
  impact/confidence/effort, confirmations and measurement; local drafts, review
  states and independently approved change observations. State is not approval.
- **Changes & results:** saved hypotheses, expected effects and later evidence
  reviews. Comparable periods show observed changes; missing evidence stays unknown.

New sites import their public colors and typography automatically, with a visible
fallback when access is blocked and a refresh control in Setup. Prepared local
page copies provide before/after review with highlighted differences. See
[reviewing together](docs/review-in-app.md). Agents may iterate on verified isolated
staging; publishing or affecting production requires exact approval under the
[website-change policy](docs/website-change-policy.md). This app has no CMS writer.

CTR is calculated from total clicks/impressions; aggregate position is impression
weighted within the same dataset. Property totals are separate from query/page
metrics. Final web data uses Pacific reporting dates with a three-day default lag.
Missing query rows do not prove zero demand. Qualified inquiries and map-pack
rankings are not supplied. Change dates do not prove causality.

Read-only setup diagnostics create no workspace/database and never refresh tokens:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent setup-check
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path secrets
```

Opening the live app stops before creating private files when protection fails.
Checks cover existing descendants, not just the parent directory. See the
[follow-up validation and next setup step](docs/mvp-live-audit-follow-up.md).

For configured sites:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent snapshot --site-id SITE_ID --days 28 --max-pages 50 --inspect
```

The legacy `snapshot --site EXACT_PROPERTY --url PUBLIC_URL --days 90 --inspect`
keeps its `data/STAMP` and `reports/STAMP` output layout and uses the same runner.
`auth`, `sites`, explicit legacy registration/migration and protected backup/restore
are documented in the setup guide.

## Validation and references

```powershell
.\.venv-mvp\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv-mvp\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-mvp\Scripts\python.exe -m pip check
```

- [Implementation/security checklist](docs/implementation-checklist.md)
- [Follow-up agent prompt](docs/mvp-follow-up-agent-prompt.md)
- [Setup, secure storage and migration](docs/setup-and-migration.md)
- [Reviewed shared mechanisms](docs/shared-playbook.md)
- [Repo-scoped seo-audit skill](.agents/skills/seo-audit/SKILL.md)
- [Original implementation plan](docs/lightweight-multi-site-app-plan.md)
- [Library choices](docs/libraries-and-skills-recommendation.md)
- [Implementation handoff](docs/implementation-agent-prompt.md)

Runtime and development dependencies are pinned/hashed separately. The crawler
uses one GET-only helper for pages, robots and sitemaps, with public IPv4/IPv6/DNS
and connection peer checks, explicit redirects, TLS verification, no ambient proxy
or credentials, and bounded request/time/size budgets. Sitemap XML rejects DTDs,
entities and external references. Imported text is data, never executable guidance.
