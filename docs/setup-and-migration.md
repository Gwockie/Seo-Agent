# Local app setup and migration

Supported MVP: one user, Windows, Python 3.13, loopback browser. There is no
deployment, CMS client, AI provider, conversion integration or paid data
source. Optional [weekly scheduling](weekly-audits.md) requires reviewed primary
rollout and Windows task setup; it starts disabled. Website actions require the exact approval process in `AGENTS.md`.

## Install and launch

Keep an existing environment until the new one passes validation. From this repo:

```powershell
py -3.13 -m venv .venv-mvp
.\.venv-mvp\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-mvp\Scripts\python.exe -m seo_agent app
```

Open http://127.0.0.1:8501. The guarded launcher pins loopback, CORS/XSRF and
telemetry settings. The committed `.streamlit/config.toml` also sets these values.
Do not expose this single-user app through a tunnel; localhost is not authentication.

For an immediately usable offline demonstration:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent app --demo
```

Demo uses `workspace/demo`, three clearly labeled synthetic sites, independent
account references and fixture metrics. It does not authorize Google or crawl any
website. Select a site, then use Setup, Target phrases, Overview & audits, and
Recommendations & changes. Run one synthetic audit, refresh history and inspect
its reports. Demo exports remain synthetic; never treat them as practice evidence.

## Protected storage prerequisite

Live audits, credential setup/migration and private backups fail closed unless the
chosen directory passes the read-only Windows check:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check
```

The check requires Allow ACL entries limited to the current Windows user, SYSTEM
and Administrators. Disk encryption is optional under the
[user-approved local policy](local-storage-policy.md). Encryption is reported
separately; an inaccessible encryption check is unknown, not proof the disk is
unencrypted. SQLite/CSV/Markdown are ordinary private files, not encrypted by
keyring. Use a local directory with verified restricted access, including its
existing contents. Do not put patient records in this app.

Verification includes every existing descendant's ACL. Encryption diagnostics
also cover existing files. Reparse points,
inaccessible entries, more than 10,000 entries, or a 30-second verification timeout
fail closed. The command creates no directory or SQLite file. A missing workspace
reports its existing parent's status but does not count as verified; configure an
existing protected workspace with the normal Windows tools before live setup.

Use read-only diagnostics for each prerequisite:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent setup-check
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path secrets
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path 'data\STAMP'
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path 'reports\STAMP'
```

`setup-check` reports only protection status, backend selection and credential
format/size. It does not probe the vault, refresh a token, contact Google, verify
account identity or certify live readiness. The live UI stops before loading
private profiles or creating workspace artifacts if protection is unavailable.

The app does not change ACLs, enable encryption or modify machine-wide settings.
You or an authorized agent/administrator can configure folder access through
normal Windows tools after reviewing the exact scope and rollback plan. OS account
compromise, admin access and shared Windows sessions remain outside the isolation
boundary. Local backups require independently verified restricted access. Protect
copies before moving them off this computer; the ZIP format itself is not encryption.
Use `storage-check --path PATH --require-encryption` if you want verification of
EFS on every entry or fully encrypted BitLocker with protection On as well.

Use a configured private workspace, including with the UI launcher:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'D:\ProtectedSEO\workspace' storage-check
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'D:\ProtectedSEO\workspace' app
```

The same protection prerequisite applies to `secrets` when writing OAuth client
configuration/authorization, and to legacy evidence folders during import. Until
verified, use the synthetic demo; do not enter private client material into local
configuration/drafts on unprotected storage.

Custom private workspaces inside this repository must remain under the ignored
`workspace`, `.tmp` or `backups` roots; other in-repository destinations are
rejected before creation. A protected directory outside the repository is also
supported. Ignore rules do not provide encryption or permission protection.

## Google accounts

Keep the Desktop OAuth JSON at `secrets/client_secret.json` (ignored by Git). Enable
Search Console API and configure the operator as a test user if applicable. Only
`https://www.googleapis.com/auth/webmasters.readonly` is requested/accepted.

Add a connection reference in Setup. Then complete consent yourself from the CLI:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent auth --connection CONNECTION_ID --account ACCOUNT_EMAIL
.\.venv-mvp\Scripts\python.exe -m seo_agent sites --connection CONNECTION_ID
```

The CLI also supports explicit setup without the UI:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent add-connection --label 'Original practice Google account'
# Copy the generated ID exactly. Authenticate or migrate only that new reference.
.\.venv-mvp\Scripts\python.exe -m seo_agent auth --connection CONNECTION_ID --account ACCOUNT_EMAIL
.\.venv-mvp\Scripts\python.exe -m seo_agent select-connection --site-id SITE_ID --connection CONNECTION_ID
```

`select-connection` validates access to the selected site's exact property before
saving its account reference; failure preserves the previous selection and other
sites. This does not infer the operator's account from a label or email hint.
If credentials are in a separate protected directory, use the global option
`--secrets 'D:\ProtectedSEO\secrets'` before the command. Only auth/migration and
the legacy credential reader use that directory; selected Vault IDs stay explicit.
Do not move or rewrite the legacy token as a setup shortcut.

IDs are generated 32-character hex identifiers, not emails or path components.
Omitting `--connection` from `auth` creates a separate ID. Reconnecting an existing
ID changes only that explicitly named account reference. `--reauth` requires an
exact connection ID. An account hint is not identity proof. Select the accessible
exact property and run the UI property validation; a URL-prefix property and
`sc-domain:` property are never silently substituted. A shared connection never
grants access to another site's database records.

Keyring must select exactly `keyring.backends.Windows.WinVaultKeyring`; other
backends and plaintext fallback are rejected. A non-sensitive round-trip probe
precedes new consent/migration. Tokens remain only in Windows Credential Manager,
outside Streamlit state, SQLite, reports, caches and backups. Refresh validates
scope and preserves the connection ID. Errors are sanitized.

This backend stores UTF-16 credentials. The adapter checks the
[2,560-byte Windows generic-credential payload limit](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw)
before writing. Oversized tokens make that
connection unavailable. No token splitting, custom encryption or DPAPI blob
adapter was introduced. A separate reviewed OS-protected blob adapter is required
if real credentials exceed the limit; do not use plaintext as a workaround.

## Original practice and historical evidence

The initial MVP worktree contained only `data/.gitkeep` and
`secrets/README.txt`, with no original URL, private reports or token. No live
migration or October 6 indexing improvement was verified.

Supply the actual original final public URL and exact property explicitly:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent seed-original --url 'ACTUAL_PUBLIC_URL' --site 'EXACT_PROPERTY'
```

This seeds the ten original Paoli/near-me targets, psychology vocabulary and an
October 6 **user-reported, unverified** observation. It does not invent clinical
facts, affected URLs or the actions taken. In the UI, the original-practice
checkbox provides the same faithful phrase seeding after explicitly selecting
psychology and Paoli. Each other site starts independently with `general` by
default; choose psychology deliberately when appropriate.

Register each historical pair without moving or rewriting it:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent register-legacy --site-id SITE_ID --data 'data\STAMP' --reports 'reports\STAMP'
```

Both paths must be the matching snapshot pair directly inside the original
repository's data/reports roots. The
manifest URL/exact property must match the selected site. A missing property or
public-only manifest needs `--associate` for deliberate association; mismatching
identities still fail. Imports preserve dates, narrative and original paths, label
old rule versions unknown, and do not claim missing performance is zero.
Both `url` and the older public-only `site_url` field are checked. When a manifest
has no full timestamp, a valid UTC snapshot folder name supplies the metadata
timestamp with its source recorded explicitly. Conflicting dates or unknown
timestamps are rejected rather than replaced with today's import date.
The SQLite collection timestamp is normalized to UTC for correct history ordering;
the original manifest is not rewritten. Current site configuration is an explicit
viewing association, not proof of the configuration/rules used historically.

For a legacy token, add a **new unused** connection reference, then:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent migrate-token --site-id SITE_ID --connection NEW_CONNECTION_ID
```

Migration checks scope, endpoint, payload size, Windows storage, property access
and round-trip retrieval before treating the copy as successful. It never deletes,
refreshes on disk or replaces `secrets/token.json`. Select the new connection in
Setup afterwards. Any legacy-token cleanup is a separate reviewable local step.
The old CLI can still read its existing token and refresh in memory without
rewriting it. New authorization writes no plaintext token. The CLI default
connection pointer is created only when no previous pointer/legacy token exists.

New site/audit records use `workspace/private/sites/<id>/audits/<id>/data` and
`reports`; legacy `snapshot --site ... --url ...` retains `data/STAMP` and
`reports/STAMP`. Both CLI and UI use `run_snapshot`. Prefer:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent snapshot --site-id SITE_ID --days 28 --max-pages 50 --inspect
```

Site URL/property identity is immutable after creation: add a separate site for
a different identity. Goals, facts, phrases, connections and allowed rule settings
can be updated. Saved audit configuration/findings stay immutable. Local draft
files and recommendation review state remain separate from exact-action approval.

## Reports, imports and backup

Phrase CSVs include a site ID. Cross-site/mixed imports fail; an unscoped CSV needs
the UI's explicit selected-site association. Imports are capped at 2 MiB/500
phrases, reject unknown columns and duplicates, and validate intended page URLs.
Related terms use JSON lists in CSV. Exported CSV text is spreadsheet-escaped;
preserved raw CSV evidence is not modified. Displayed reports are literal text.

Audit packets contain only the selected audit's reports/evidence. Treat downloaded
packets as private. Property totals, query-only totals, and query/page metrics use
separate aggregations; they cannot be added together. Reports show source failures,
row limits, final-data Pacific windows and measurement limitations. Change markers
show observations alongside performance without claiming causality.
HTTP 202 responses, robots-blocked pages and request failures keep the public crawl
partial even when Google data succeeds; they cannot verify current page content.
Separately prepared `reviewed-executive-summary.md`, `reviewed-recommendations.md`
and `reviewed-proposed-edits.md` appear in the selected audit's report menu when
present, without replacing generated reports. A labeled
`reviewed-page-observations.json` supplement is included in scoped packets/backups.
Reviewed browser observations do not change the raw crawl's recorded status.
The **Recommendations & changes** view also has **Review together**, with plain
labels for the selected audit's reviewed summary, recommendations and proposed
edits. Reading or saving a document does not approve implementation. See
[reviewing together in the app](review-in-app.md) for the one-click starter and
the remaining read-only collection step.

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent backup 'D:\EncryptedBackups\seo-backup.zip'
.\.venv-mvp\Scripts\python.exe -m seo_agent restore 'D:\EncryptedBackups\seo-backup.zip' 'D:\ProtectedSEO\restored'
```

Backup requires access-restricted source/destination directories, excludes OAuth client
files/tokens, and retains profiles, evidence, reports, states and changes, including
registered legacy evidence. It also preserves saved HTML/text page captures,
robots/sitemap evidence and historical validation metadata as inert files. Report
packets still contain only the selected CSV/Markdown/JSON reporting subset, with
spreadsheet-safe CSV exports; they are not full backups. Protection of registered
legacy folders is rechecked before backup. Restore checks archive and destination
storage, requires a new directory, rejects traversal,
symlinks, unknown contents, excessive expansion and invalid database relationships.
It remaps audit paths and detaches active Google connection references. Reconnect
explicitly even on the same machine; another machine cannot rely on the previous
user’s vault. Keep the original backup until restored evidence has been checked.

## Development validation

```powershell
.\.venv-mvp\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv-mvp\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-mvp\Scripts\python.exe -m pip check
.\.venv-mvp\Scripts\python.exe -m pip_audit -r requirements.lock --disable-pip --no-deps
```

Set TEMP/TMP to a writable local scratch directory if a sandbox cannot use the
Windows temporary directory. Streamlit AppTest worker/subprocess behavior may
require a normal local terminal outside that sandbox; tests use only synthetic
fixtures. Dependencies were resolved on Windows/Python 3.13 using pip-tools;
runtime and development locks include hashes. Regenerate with `--generate-hashes
--strip-extras --no-emit-index-url --no-emit-trusted-host`; add `--allow-unsafe` for
the development lock's packaging tools, then review, install and re-test.

See `docs/implementation-checklist.md` for actual validation and limits.
