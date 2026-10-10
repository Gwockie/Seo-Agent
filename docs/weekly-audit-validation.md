# Weekly audit validation

## Completeness correction — October 10, 2026

Successful ancillary non-HTML responses are recorded explicitly and counted
separately from usable HTML content. They no longer falsely make crawl coverage
partial because they lack an HTML title. They cannot satisfy priority landing
pages, and failed requests, unavailable HTML, missing priority pages or a crawl
with no HTML content remain incomplete. Mislabeled HTML challenges also remain
unavailable rather than receiving the non-HTML exemption.
Safely parsed supported KML/sitemap XML roots also identify structured resources
when the server supplies an incorrect HTML content type. Embedded HTML inside a
KML description does not turn the XML document into an unavailable webpage.

The canonical stable runtime passed **183 tests**, including the existing
22 AppTest cases and three new completeness regressions, in 69.434 seconds.
The new tests cover the actual synthetic crawler-to-snapshot path and seven
failure/coverage cases. A restricted full-suite run stalled and was stopped;
the successful full run used the normal Windows user with isolated synthetic
workspaces. No live credentials or evidence were used by these tests.
Private installation rollout, live source outcomes and scheduler records remain
in protected local storage; they are not public GitHub artifacts. The dated
development status below describes October 9, not a current installation's
activation state.

## Original development validation — October 9, 2026

Validated October 9, 2026 on Windows with an isolated Python 3.13 environment
installed from the existing hash-pinned `requirements-dev.lock`. Development used
the managed worktree based on current `origin/main`, synthetic workspaces and a
separate loopback Streamlit port (8517). No dependency or lockfile changes.

## Automated checks

The final full command was:

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv-weekly\Scripts\python.exe -m unittest discover -s tests -v
```

- Full suite: **180 tests passed in 160.525 seconds**, including **22 Streamlit AppTest cases**
  (14 existing app, five tracking, three weekly controls).
- Focused weekly regressions: **34 passed in 18.322 seconds** before the last
  backward-clock regression, which is included in the full suite. Earlier focused
  runner/tracking, credential and UI checks also passed; overlapping runs are not
  counted as additional tests.
- `pip check`: no broken requirements. `compileall`: passed for app, source and
  tests. CLI help/argument checks for weekly schedule and task review: passed.
  `git diff --check`: passed.

Coverage includes disabled defaults, independent site settings/history, explicit
bounds, IANA timezones, DST folds/gaps, backward clock changes, restart/missed-week
catch-up, duplicate triggers, fresh retry identities, capped/long-delay retry,
partial/failed/unavailable source stages, empty/missing coverage, interrupted
bookkeeping/checkpoints, pre-audit failures, immutable last-complete history,
separate-process workspace contention, migration ordering and restored schedules
remaining disabled without an installation contract.

Mocked credential tests cover normal and mid-job refresh, exact scope checks,
revocation, network failure, payload overflow, Vault writes and read-back failure,
sanitized categories and preservation of other connections. Temporary Google and
public requests are bounded; long Retry-After on the final Google attempt is
retained. Unsafe destination/TLS failures stop recovery. Challenge/unfinished
responses do not become extracted content or indexing/change evidence.

The supervisor tests include an actual separately launched hung synthetic child
that is killed/waited for, followed by interruption reconciliation and a released
gate. No real network hang or Google credentials were used.

An intermediate Windows run reproduced a sharing violation during atomic manifest
replacement. The final implementation retries that specific failure six times
with at most 1.55 seconds total backoff; a regression verifies recovery and that
exhaustion preserves the prior checkpoint. The asynchronous UI test waits for
completion with a bounded deadline rather than assuming a job finishes in four
seconds. The final suite passes with both corrections.

## Windows and real-browser checks

Task registration/update/disable/remove are mocked in tests. Review-digest drift,
identity checks, protected rollback, stable absolute paths including spaces,
principal/logon/power/timeout settings and wrong roots/workspaces/interpreters are
covered. Windows Task Scheduler accepted generated synthetic XML through an
unregistered `Schedule.Service.NewTask(0)` definition's `XmlText` setter. This
validates XML parsing/schema, not registration, user permissions or a scheduled
launch. No task was registered as a test side effect.

A separate real browser used only the synthetic app. It saved a disabled schedule,
launched one weekly Run now collection, observed its own-site complete audit and
all five source outcomes, and retained exactly that attempt through UI reruns and
server restart. A fresh browser load showed disabled status and local next/last
times, with no browser console errors. Earlier restart health warnings were
expected while this task's own synthetic server was stopped. Screenshots and raw
logs remain ignored local artifacts; no fixture IDs or logs are published.

## Live status and remaining setup

**Weekly automation is not active.** No primary database was opened/migrated, no
primary process restarted, no live audit performed and no live Task Scheduler
registration changed. The actual scheduled principal's Vault read/refresh
persistence, OAuth publishing status, task registration and subsequent scheduler
tick remain unverified. The existing October 9 audit with temporary adapters is
not certification of the ordinary worker.

The next setup step is to obtain the human's release of the primary workspace for
the coordinated rollout and exact reviewed activation in
[weekly-audits.md](weekly-audits.md#concrete-activation-packet). That packet includes
idle checks, protected rollback before migration, canonical primary paths,
read-only Google publishing-status review, selected site/time, exact task preview
and digest, one bounded ordinary live audit under the chosen principal, status
verification and separately reviewed disable/remove rollback. Keep schedules
disabled until that coordinated setup is authorized and completed.
