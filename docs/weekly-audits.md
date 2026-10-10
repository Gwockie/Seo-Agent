# Weekly read-only audits

Weekly collection uses the app's deterministic Python runner and Windows Task
Scheduler. It needs no Codex, model, Streamlit window or browser website sign-in.
New site schedules are disabled. Monday 09:00 America/New_York is an editable
suggestion, never an activation performed by opening the app.

## What the user sees

Select the site and open **Overview & audits → Weekly read-only audits**. Save
its weekly day, local time and IANA timezone, explicitly choose enabled/disabled,
run one audit now, or disable future collections. The panel shows next due,
overdue, last attempt, last complete collection, retry time, failure reason and
own-site attempt/source history. Refresh history after a job finishes. The separate
**Check Windows task status** button reads registration, next dispatcher tick and
Windows result; reruns never register tasks or repeat collection requests.

Every collection uses the selected saved connection and exact property, the exact
`https://www.googleapis.com/auth/webmasters.readonly` scope, 28-day final web
comparison windows and a three-day Pacific reporting lag. Settings allow at most
50 public pages and 20 priority-first inspections. Priority landing pages precede
discovered crawl pages. Each site's saved settings and evidence stay independent.

## Availability and timing

One identifiable task checks all enabled site schedules every 15 minutes and at
the operator's logon. Python evaluates weekly local time in each saved IANA zone,
independently of the machine's display timezone. Collection begins at the first
available check on or after that time, normally within 15 minutes. This avoids
fixed UTC offsets drifting through DST. A repeated local time uses its first
occurrence; a nonexistent time advances to the first valid local minute.

The first version uses **InteractiveToken / LeastPrivilege**, with the selected
Windows user remaining signed in. A locked desktop can run; signing out prevents
that context from running. Sleeping or powered-off machines cannot collect. The
task does not wake the machine or change its power policy, and requires AC power.
Missed schedules catch up once when available, rather than replaying missed weeks.
For timely collection while this computer is unavailable, a separately reviewed
always-on installation would be needed; cloud hosting is outside this feature.

## Durable state, recovery and source honesty

Schema version 3 adds only `weekly_schedules` and `weekly_attempts`. Attempts retain
scheduled/start/finish times, fresh request/audit IDs, source outcomes and sanitized
failure categories, including failure before an audit exists. Identical trigger
IDs are deduplicated. Genuine retries get new immutable evidence/output IDs.

Only complete required Google current/previous performance, sitemap listing,
bounded crawl coverage and requested inspections update last complete. Empty
performance exports are a completed request with demand unknown. Crawl needs
usable content, no unavailable selected pages and no missing configured priority
pages; inspections need every requested result without collection errors. A
Google verdict of FAIL/noindex can be fully collected evidence: completeness is
not indexing or SEO health. A 50-page budget is bounded coverage, not certification
of every page on a large website. Independent successful sources remain usable
when another fails. Atomic stage checkpoints survive interruption.

Content challenges, unfinished HTML, robots restrictions and missing page content
never become content/noindex/deletion/outside-edit evidence. The existing honest
user agent, GET-only public DNS/socket-peer/host/robots/TLS/redirect/size/request
boundaries remain in force. No cookies, credentials, CAPTCHA bypass or host
security changes are used. No immediate retry follows a challenge or HTTP 202/403.

Google transport/refresh calls have 20-second timeouts. Google requests make at
most three attempts with short backoff; public temporary responses make at most
two, both counted against request budgets. Retry-After is honored; delays beyond
60 seconds for Google or 30 seconds for public requests defer instead of shortening
the server's delay. Longer Retry-After values persist across worker attempts;
values beyond seven days require review instead of earlier automatic retry. A supervisor kills and waits for its own collector at 900
seconds/site, with 1800 seconds total dispatcher runtime. Windows' outer timeout
is 35 minutes. Successful independent exports survive a killed collector.

Temporary collection failures can retry after 15 minutes and then one hour (three
collection attempts per due occurrence). Busy work returns exit 75/deferred,
creates no failed collection, and waits for a later dispatcher check. A failed
attempt preserves last complete and the original overdue due time. Interrupted
jobs reconcile only after acquiring the coordination gate; completion is never
invented, even if an audit finished before bookkeeping was interrupted. Access,
storage/configuration problems and challenges stop automatic retries. Exhaustion
also requires resolving the issue and explicitly reviewing/saving the schedule
again; it does not quietly move the due time to next week.

## Concurrency and rollout prerequisites

Audits, public tracking checks, backups, restores and Store migration now share
the resolved workspace's sibling `<workspace-name>.operation.lock` across
checkouts/processes. Current-schema Store opens can read while a job runs;
additive initialization/migration acquires the gate before SQLite schema writes.
The collector holds the gate once and passes `already_locked=True` to run_site,
tracking and Store; it never takes a second non-reentrant copy. Backups include
schedule/attempt history but exclude installation/task rollback files and tokens.
Restore disables schedules, detaches connections and requires explicit new setup.

**Do not roll out alongside an old running primary app.** Old loaded code still
uses its former checkout lock. Obtain release of the primary workspace from the
SEO work, verify audit/tracking/backup jobs idle, create and verify a protected
rollback backup with the old source, then update and restart/migrate the primary
app deliberately. Do not stop another chat's processes. Rolling source back alone
does not downgrade SQLite; restore the pre-migration backup to a new protected
directory with the matching old build. Development must never open/migrate that
primary database, copy ignored assets or point a task at a disposable worktree.

## Concrete activation packet

The primary installation is `C:\Personal Projects\seo-agent\local-seo-agent`.
After its release, run the following from that installation as the chosen normal
Windows user. Replace SITE_ID with the app-validated selected site's ID only;
keep IDs, outputs and rollback files in protected local storage, never GitHub.
Use the configured protected workspace if it differs from the default shown.

```powershell
$seoRoot = 'C:\Personal Projects\seo-agent\local-seo-agent'
$seoPython = Join-Path $seoRoot '.venv-mvp\Scripts\python.exe'
$seoWorkspace = Join-Path $seoRoot 'workspace\private'
$seoInstallation = Join-Path $seoWorkspace 'weekly-installation.json'
Set-Location -LiteralPath $seoRoot
& $seoPython -m seo_agent --workspace $seoWorkspace storage-check
# First Store open after the protected rollback backup performs the gated migration.
& $seoPython -m seo_agent --workspace $seoWorkspace weekly-save --site-id SITE_ID --weekday 0 --time '09:00' --timezone 'America/New_York'
& $seoPython -m seo_agent --workspace $seoWorkspace weekly-install
& $seoPython -m seo_agent weekly-task-preview --installation $seoInstallation --action register
```

`weekly-install` writes only the protected credential-free installation contract;
it refuses worktree `.git` files, demo, missing stable runtimes or replacement of
an existing contract. Worker launches revalidate its exact root, workspace, stable
`.venv-mvp` Python executable, current Windows SID and protected storage before
Store construction. Each run revalidates saved site bounds/configuration,
connection/scope and exact property access. Wrong roots/principals fail closed.

The task preview supplies the exact identifiable name, current XML/status, proposed
XML, absolute executable/arguments/working directory, principal, timing, power,
retry/timeout and rollback, plus `reviewed_sha256`. The action launches
`C:\Personal Projects\seo-agent\local-seo-agent\.venv-mvp\Scripts\pythonw.exe`
without a console with `-m seo_agent weekly-worker --installation` and the absolute
protected installation file. No Windows password, administrator/SYSTEM task or
credential is stored in arguments/XML/SQLite/logs/exports. A task with mismatching
description/principal/action paths is not treated as this app's task. Changed XML
invalidates review. Installation files are not part of backup/restore.

Before enabling, inspect the OAuth app's **Audience / Publishing status** read-only
in Google Cloud for this connection's existing client. Google documents that
external applications in Testing can issue seven-day refresh tokens for this
scope. Refreshing today is not proof of indefinite access. Do not change publishing
status/scopes or replace a connection merely to test. Prepare any required change
or exact reconnection separately for human authorization. Vault overflow/write or
round-trip failure stops that connection; there is no plaintext fallback or silent
account replacement. Reconnect explicitly with `auth --connection CONNECTION_ID
--reauth` only after review; other sites/connections remain unchanged.

After the user approves this exact task registration and selected weekly time:

```powershell
& $seoPython -m seo_agent weekly-task-apply --installation $seoInstallation --action register --reviewed-sha256 REVIEWED_SHA256
& $seoPython -m seo_agent --workspace $seoWorkspace weekly-save --site-id SITE_ID --weekday 0 --time '09:00' --timezone 'America/New_York' --enable
# Exactly one ordinary bounded audit, under the same signed-in Windows principal:
$seoTrigger = [guid]::NewGuid().ToString('N')
& $seoPython -m seo_agent weekly-run-now --installation $seoInstallation --site-id SITE_ID --trigger-id $seoTrigger
& $seoPython -m seo_agent --workspace $seoWorkspace weekly-status --site-id SITE_ID
& $seoPython -m seo_agent weekly-task-preview --installation $seoInstallation --action register
```

Verify this audit and honest source status in own-site history, the current task
principal/status/next dispatcher tick and next weekly due time. This tests the
ordinary supervised collector with real Vault read/refresh persistence in that
principal, without temporary adapters or browser fetching. Actual Task Scheduler
launch must also be observed at its next due tick before claiming it ran through
the scheduler. Do not repeat live audits to poll status. Existing October 9 temporary
in-process adapters and mocked tests do not certify this path. If access/activation
cannot be verified, leave the schedule disabled and report the precise remaining
setup action. No live task or normal primary audit was installed/run in development.

## Exact disable/remove rollback

Disabling the site stops future collections; it does not erase history or terminate
an audit already running. Disable the dispatcher independently to stop future
automatic launches for all schedules in this workspace. Removing it deletes only
the previewed, identity-checked app task, preserving site history and credentials.
Preview each action and use its own newly reviewed digest:

```powershell
& $seoPython -m seo_agent --workspace $seoWorkspace weekly-disable --site-id SITE_ID
& $seoPython -m seo_agent weekly-task-preview --installation $seoInstallation --action disable
& $seoPython -m seo_agent weekly-task-apply --installation $seoInstallation --action disable --reviewed-sha256 DISABLE_REVIEWED_SHA256
# Optional removal after reviewing that separate exact packet:
& $seoPython -m seo_agent weekly-task-preview --installation $seoInstallation --action remove
& $seoPython -m seo_agent weekly-task-apply --installation $seoInstallation --action remove --reviewed-sha256 REMOVE_REVIEWED_SHA256
```

Each task mutation preserves credential-free prior XML in a protected local
`weekly-task-rollback-*.json` file. Updating/re-registering requires a fresh exact
preview; it never happens on a Streamlit rerun. Never register a task for a restored
installation automatically. This feature sends no messages or external notifications.

References checked during implementation: [Microsoft Task Scheduler overview](https://learn.microsoft.com/en-us/windows/win32/taskschd/about-the-task-scheduler),
[task XML schema](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema),
[RegisterTask API](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertask),
[Google refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration).
See [validation](weekly-audit-validation.md) for actual results and limits.
