# Local SEO Agent — Stage 2

A local SEO audit project that pulls live Google Search Console data and crawls a public WordPress site.

The Python auditing tool does **not** modify WordPress. Agents may implement website
changes only after explicit human approval of the exact actions, as defined in
[AGENTS.md](AGENTS.md). Search Console access remains read-only.

## Local audit outputs

Audit reports and implementation handoff prompts live under `reports/` and remain
local. They can contain private Search Console performance and indexing information
and are not included in the public repository.

Raw Search Console exports and downloaded page evidence under `data/`, OAuth
credentials/tokens, temporary files, and `.venv` also remain local and ignored.
Collect your own authorized snapshot after cloning the project.

## 1. Create the Google Cloud OAuth credential

In Google Cloud:

1. Create/select a project.
2. Enable **Google Search Console API**.
3. Configure the Google Auth consent screen.
4. If the app is in Testing mode, add the Google account that has access to the Search Console property as a test user.
5. Create an OAuth Client ID with application type **Desktop app**.
6. Download the JSON and save it as:

   `secrets/client_secret.json`

Do not commit this file.

## 2. Install

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activation is optional. On Windows, you can run every command below with
`.\.venv\Scripts\python.exe` instead of `python`.

## 3. Authorize

```bash
python -m seo_agent auth
```

A Google browser consent window opens. The app requests only:

`https://www.googleapis.com/auth/webmasters.readonly`

The resulting refresh/access token is saved locally at `secrets/token.json`.

Complete consent within five minutes. If authorization expires or is revoked,
remove the local `secrets/token.json` and run `auth` again. The client credential
must be a Desktop app JSON, with that exact filename (avoid `.json.json`).
The account must be an OAuth test user when the app is in Testing mode.

If `sites` returns no properties because the wrong account was authorized, switch
accounts with `python -m seo_agent auth --reauth --account ACCOUNT_EMAIL`.
The existing token is replaced only after new consent succeeds. An account hint
suggests a login; confirm the selected account in the browser.

## 4. Find the exact Search Console property identifier

```bash
python -m seo_agent sites
```

Use the exact property value returned. A domain property looks like:

`sc-domain:example.com`

A URL-prefix property looks like:

`https://www.example.com/`

## 5. Run a live audit snapshot

```bash
python -m seo_agent snapshot \
  --site "sc-domain:example.com" \
  --url "https://example.com" \
  --days 90 \
  --inspect
```

On Windows, put it on one line if preferred.

The tool pulls:
- Search Console query + page performance
- query-only and page-only performance
- device/country/date performance
- submitted sitemap metadata
- a public site crawl
- optional Google URL Inspection results

It writes timestamped data to `data/` and a mechanical summary to `reports/`.

## 6. Hand the repository to Codex

Ask Codex:

> Follow AGENTS.md. Run a fresh snapshot for the configured site, analyze the latest timestamped data, inspect the most important public pages, and create the three requested reports. Do not make any external changes.

## Cost

This project uses the Google Search Console API plus public HTTP requests. There is no Semrush/Ahrefs dependency.

## Notes

Search Console is not a complete rank tracker: its API returns Google's Search Console performance data and is subject to Google's aggregation/data limits. It is still the best source of truth for how this specific property is actually appearing in Google.

Reporting dates use Pacific time, matching Search Console. A 90-day window is
inclusive and ends three days before the current reporting date by default.
Query exports omit anonymized queries; missing queries do not prove zero demand.
Exports are capped at 50,000 rows per dataset and use final web-search data.

The crawler stops if robots.txt cannot be fetched (except a missing 404 file),
checks robots rules and host boundaries before page/sitemap redirects, and records
HTTP X-Robots-Tag directives and outgoing internal-link URLs. Robots crawl delays
apply to the page crawl. Cross-host redirects are recorded as errors; use the
website's final public hostname for `--url`. Inbound-link counts reflect only the
sample actually crawled, not the full site.

Local validation:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```
