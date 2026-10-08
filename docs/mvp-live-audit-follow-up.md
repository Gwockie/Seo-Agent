# Live-audit follow-up

"Operator" means you: the person using this app on your Windows computer.
Windows permissions control which computer accounts can open the private files.
Encryption protects the saved files if someone accesses the drive. You approved
making disk encryption optional for local use. Restricted folder access remains
required before using private Google data; the approved folders now pass. See the
[current local storage policy](local-storage-policy.md).

## Current checkpoint: October 8, 2026

With explicit user approval, access to `secrets`, `data`, `reports` and the new
`workspace/private` was restricted to the current Windows account, SYSTEM and
Administrators. Original permissions were saved locally for rollback. All 49
original files remained byte-identical, with none added, missing or moved in
those original roots. Encryption was not enabled. The app itself still makes no
automatic permission changes.

The original practice was explicitly configured with its exact URL-prefix
property and ten preserved phrases. Its existing read-only credential was copied
into a new unused Windows Vault connection, retrieved and validated against that
exact property before selection. The original token remains unchanged; no new
consent or broader scope was required. Two historical audits were registered in
place with their original collection dates and unknown historical rule versions.
Clinical facts remain unconfirmed.

A bounded live audit collected final web performance for equal 28-day Pacific
calendar windows and read-only URL Inspection for the two selected priority
service pages. Google performance, sitemaps and inspection completed. The overall
audit remains **partial** because the automated public crawl received HTTP 202
without usable page content. Both service pages rendered in a normal browser;
those observations are saved separately and do not change the raw crawl status.
No indexing improvement or effect of the user-reported October 6 fixes is claimed.

Three reviewed reports and a labeled page-observation supplement were saved
inside the selected audit, preserving all generated reports and raw exports.
The report menu exposes these files only for their associated site and audit,
as literal text. A local unencrypted, credential-free backup preserves all three
audits; 72 archived evidence files matched their sources and no credential values
were found in the archive. Private identities, evidence, reports, credentials
and backup files remain excluded from Git publication.

The necessary local fixes validate the older `site_url` identity field, preserve
UTC folder timestamps when old manifests record only a date, reject conflicting
or unknown dates, label unavailable public crawling partial, and retain reviewed
observations in scoped packets/backups. The final full suite passed **63 tests**
in 30.308 seconds, including seven Streamlit AppTest scenarios and the six
original tests. Dependency consistency, compilation and whitespace checks passed.
Dependencies and locks did not change; no new vulnerability scan was performed.
The real browser check selected the original practice and displayed the saved
partial audit, source statuses, priority-page inspections and reviewed executive
summary. Socket inspection verified loopback-only binding at `127.0.0.1:8519`;
the temporary tab and its server process tree were closed afterwards. A final
recursive access check passed for all four private roots, including the new
reports and backup; the original-file comparison still passed.

Your next step is to review the saved proposed edits and confirm the actual
clinical services before approving any exact website changes. An agent can handle
the app commands. The remaining technical step is to obtain a successful bounded
read-only public crawl, or a verified technical export, before claiming a complete
website audit. Do not infer empty content or page-level `noindex` from the
unfinished HTTP 202 response. No website write, sitemap change or indexing request
was made. The scope remains exactly `webmasters.readonly`.

A subsequent October 8 readiness pass restored a separate protected copy of the
backup, verifying all 72 evidence files and three audits without changing the
working connection. The public probe stopped at CAPTCHA-related HTTP 202 from
`robots.txt`; the crawler now rejects incomplete robots responses. The app has a
direct **Review together** section and a one-click starter. Its full suite passed
65 tests; see [reviewing together in the app](review-in-app.md) for the current
review workflow and precise hosting/security diagnosis step.

## Historical checkpoints

The October 7 notes below describe earlier blocked prerequisites and are retained
as history. Their live-access limitations were superseded by the October 8 checks
above. This public note contains no private practice data or account identity.

## Starting point and reviewable fixes

The initial MVP and the first follow-up were committed and merged to `main` in
[PR #1](https://github.com/Gwockie/Seo-Agent/pull/1). The dated validation below
records that earlier checkpoint; it is retained as historical evidence. The
subsequent encryption-policy change keeps access checks mandatory and reports
encryption separately. Plaintext files no longer block approved local operation.

The primary checkout was on the pre-MVP `main` branch. The requested follow-up
prompt and working MVP were located on `codex/multi-site-seo-mvp`. Work continued
from that implementation on `codex/mvp-live-audit-follow-up`. At the validation
checkpoint, the follow-up changes had not yet been committed or pushed. The
previous worktree's missing-asset limitations are historical: the
primary checkout contains original audit/report folders and legacy OAuth files.
Their presence does not establish current Google access or authorized identity.

- Protected storage now gates workspace/database creation as well as profile,
  audit and credential writes. The live UI stops before opening private state
  when the prerequisite fails. `storage-check` creates no directory/database.
- Windows verification covers existing descendants' ACLs and encryption. A
  plaintext child, broad child ACL, reparse point, inaccessible entry, bounded
  scan limit or verification timeout fails closed. Missing paths report their
  existing parent's status and remain unverified. No ACL/encryption was changed.
- `setup-check` reports storage, backend selection and credential format/size
  without printing tokens, probing the vault, refreshing or contacting Google.
- `add-connection` and `select-connection` support explicit CLI setup. Selection
  saves only the named site's connection after validating exact property access.
  `--secrets` selects a protected credential directory; unignored in-repository
  credential paths are rejected. Legacy/default CLI credential access is gated.
- Historical imports require matching data/report snapshot pairs. Their UTC
  metadata dates sort correctly without rewriting source manifests. Unknown
  historical rule/configuration versions stay explicitly unknown, rather than
  being attributed to current rules. Completed/restored audits cannot be finished
  again to overwrite their collection status.
- Backups preserve inert HTML/text page captures, robots/sitemaps and historical
  validation metadata alongside CSVs, reports and SQLite history. Tokens/client
  credentials are excluded; restored Google connections remain detached.
  Registered historical storage is rechecked before backup. Archives and restore
  destinations require protected storage.
- The shared snapshot runner refuses existing nonempty outputs before collecting
  or writing. Legacy output names now include microseconds to reduce collisions.

## Checks actually performed

- Installed the existing pinned, hash-checked development lock in a separate
  `.venv-mvp`, retaining `.venv`; `pip check` passed. Dependency versions/locks
  were not changed. The initial MVP vulnerability scan is a prior baseline;
  no new vulnerability scan was performed for these code-only fixes.
- Final full suite: **55 tests passed** in 22.266 seconds, including nine new
  follow-up regression tests, five Streamlit AppTest scenarios and the six original
  tests. CLI help, Python compilation and Git whitespace checks passed; private
  credential/evidence paths and the separate environment remain ignored by Git.
- A sandboxed suite stalled at AppTest. Only its identified test processes were
  stopped; validation was repeated in the normal local process context with
  synthetic fixtures. No real account or client data was used in tests.
- Real loopback browser check displayed the protection warning and blocked live
  setup, with no profile/audit controls exposed. `workspace/private` stayed absent.
  Socket inspection confirmed `127.0.0.1:8517`; the temporary tab/server were closed
  after verification.
- Read-only Windows diagnostics in both sandbox and normal local context found broad ACLs and no verified encryption on
  credential and historical-evidence entries. BitLocker status was unknown, not
  proof the volume is unencrypted. Windows WinVaultKeyring was selected, but a
  current access probe, real token migration and Google property access were not
  attempted while storage remained unverified.
- Legacy credential format/read-only scope and the saved payload size fit the
  backend limit. This is not proof that refresh/consent/access will succeed or
  that a refreshed credential will fit. No token contents were displayed.
- All **49 original files** under data/reports/secrets remained byte-identical in
  read-only fingerprint comparison, with no new files in those roots. No original
  evidence file was moved or rewritten.

## Earlier policy checkpoint and setup reference

Subsequent user-approved policy validation: **58 tests passed** in 32.944 seconds,
including an unencrypted-access Store regression, an explicit encryption diagnostic
and an AppTest check that a missing account keeps collection disabled. Dependency,
compilation and whitespace checks passed. A real loopback browser check displayed
the updated access warning and optional-encryption notice without exposing private
setup/audit controls. The temporary server/tab were closed and no private workspace
was created. Read-only checks still found broad permissions on the credential and
historical folders. No folder permissions, original files, Google credentials or
website settings were changed; live access remains untested.

At that earlier checkpoint, a reviewed folder-only permission plan awaited
approval. The user subsequently approved it and the October 8 section records
its application and the completed setup. The commands below remain reference
instructions for another protected workspace, not a request to repeat setup.

Configure an **existing protected workspace** and protect the original `secrets`,
`data` and `reports` folders **including their existing contents** using normal
Windows tools. Allow access only to the operator, SYSTEM and Administrators;
disk encryption is optional. An inaccessible or broad access check remains a
blocker. An agent can make a reviewed, reversible folder-only change with your
approval; you do not need to understand or run the commands yourself. Do not move/delete the legacy
token or rewrite historical folders. If using an external workspace, substitute
its actual path consistently in every command below.

Read-only verification, from the project directory:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' storage-check
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path secrets
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path data
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path reports
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' setup-check
```

Do not advance until the relevant storage checks report `verified: true`.
`setup-check` always reports live access as untested; it is not an authorization
or readiness certificate. The operator supplies/explicitly selects the original
practice's public URL and exact property; historical manifests are a reference,
not a silent account selection.

After protection passes, use this explicit sequence (global `--workspace` applies
to **every** command; add `--secrets` consistently if needed):

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' seed-original --name 'CONFIRMED_PRACTICE_NAME' --url 'CONFIRMED_PUBLIC_URL' --site 'CONFIRMED_EXACT_PROPERTY'
# Record the returned SITE_ID. This seeds goals, not clinical facts.
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' add-connection --label 'Original practice Google account'
# Record this NEW_CONNECTION_ID; it must have no existing Vault credential.
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' migrate-token --site-id SITE_ID --connection NEW_CONNECTION_ID
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' sites --connection NEW_CONNECTION_ID
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' select-connection --site-id SITE_ID --connection NEW_CONNECTION_ID
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' register-legacy --site-id SITE_ID --data 'data\STAMP' --reports 'reports\STAMP'
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' app
```

Register each matching historical pair separately, preserving the original path
and collection date. A public-only snapshot requires explicit `--associate` and
still supplies no historical Search Console evidence. If migration fails, retain
the source token. The operator can complete `auth --connection NEW_CONNECTION_ID
--account ACCOUNT_EMAIL` in the browser, then repeat the exact property validation;
no other account is selected automatically. Do not bypass a token-size rejection.

In Setup and Target phrases, confirm intended assessment/testing and therapy
landing pages from public evidence and clinician-confirmed service facts. This
makes those pages first in bounded URL Inspection and activates priority-page
relevance/alignment checks. Keep the October 6 fixes user-reported until their
exact pages/actions have supporting evidence.

Then collect a bounded read-only audit:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace 'ACTUAL_PROTECTED_WORKSPACE' snapshot --site-id SITE_ID --days 28 --max-pages 50 --inspect --inspect-limit 20
```

Inspect the source statuses before interpreting the three generated reports.
Use the repo `seo-audit` skill with the explicitly selected site's saved evidence
and rules. Cite that audit's CSV rows/rule versions; keep old human reports and
the new interpretation separate. A partial source, missing query row, public
fetch or change date does not prove clean indexing, zero demand or improvement.
Website edits still require the exact approval packet and human approval from
`AGENTS.md`; no local state or migration grants that permission.
