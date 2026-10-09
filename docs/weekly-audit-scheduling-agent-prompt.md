# Build reliable weekly audits

Recommended setup: **GPT-6.1 Sol** (`gpt-6.1-sol`), **High** effort (`high`).
Select these in the task composer. This task needs careful reasoning about durable
jobs, Windows credential access, missed runs and concurrent processes. This is a
task-specific recommendation, not a benchmark against other models.
[Model](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[effort guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Start this task in an isolated worktree from current `origin/main`. The companion
[SEO optimization task](meadow-and-mind-optimization-agent-prompt.md) owns the
primary protected workspace. Development can run in parallel; live activation and
primary database migration cannot.

## Copyable prompt

```text
Build reliable weekly read-only audits into the local SEO app. Carry out the
implementation and validation, not only a design. Use Windows Task Scheduler to
launch the app's own deterministic Python worker; weekly collection should not
require Codex, an LLM, a browser session or an open Streamlit window.

Read AGENTS.md, README.md, docs/website-change-policy.md,
docs/local-storage-policy.md, docs/setup-and-migration.md,
docs/automatic-change-tracking.md, docs/tracking-validation.md and
docs/weekly-and-seo-parallel-handoff.md. Inspect current code before assuming an
older prompt's limitations still apply. Change tracking and its review fixes are
already merged. The documented 142-test result is a dated baseline, not your new
validation.

Use a separate managed worktree/branch based on current origin/main, reusing a
suitable attached worktree when possible. Develop with isolated synthetic data
and a separate loopback port. Do not read another site's private data, copy ignored
assets into your worktree, load real credentials, open/migrate the primary
database, run live audits or restart the primary app during parallel development.
The companion SEO task alone owns live collection and protected evidence at
C:\Personal Projects\seo-agent\local-seo-agent. Do not send another chat messages
without human authorization; use saved handoffs and current Git state.

Own scheduling modules, runner/CLI integration, bounded credential-refresh/Google
timeout changes if demonstrated necessary, minimal app UI/storage/backup changes,
tests and scheduling docs. The SEO task owns private interpretation and previews,
not those source files. Report any necessary source overlap before editing it.
Avoid unrelated tracking redesign, CMS integration, cloud hosting and dependencies
unless a concrete requirement justifies them.

Implement:

1. A persistent, site-scoped schedule and headless worker using the existing
   run_site engine with explicit saved site/connection/property context. Store no
   credentials in arguments, task XML, SQLite, logs or exports. Revalidate protected
   storage, exact read-only scope/property access and configured bounds on every
   run. Reject demo/live workspace confusion and wrong execution roots. Default
   new schedules to disabled; support an explicit per-site weekly day/time and
   timezone. Propose Monday 09:00 America/New_York as an editable initial choice,
   not as an already activated schedule. Start with 28-day final web windows,
   three-day data lag, at most 50 pages and at most 20 priority-first inspections.
   Preserve per-site settings and historical evidence independently.

2. Durable attempts and due-state handling. Record scheduled time, start/finish,
   request/audit identity, source outcomes, last attempt, last complete collection,
   next due time and sanitized failure category. Preserve attempts that fail
   before an audit exists. Make repeated triggers/reruns idempotent, but give a
   genuine retry fresh evidence/output identities; do not reuse an audit request
   ID that would just return the previous partial audit. Reconcile interrupted
   jobs without inventing completion. Handle clock/timezone/DST changes, app
   restart and missed weeks; catch up once rather than replaying every missed run.
   A failed attempt must not reset the last successful collection or conceal an
   overdue schedule.

3. Cross-process concurrency. Serialize scheduled/manual audits, tracking checks,
   backup and any required migration. The existing lock is checkout-scoped: do
   not assume it protects the same workspace when launched from another checkout.
   Restrict live launches to the canonical primary installation, or introduce a
   reviewed workspace-scoped lock used consistently by all relevant callers.
   Distinguish busy/deferred from failed and retry after contention without
   duplicating collection. Do not hold a second copy of the same non-reentrant
   lock around run_site. Review Store construction/migration order too; a scheduler
   must not migrate a database before acquiring the required coordination gate.

4. Honest success and bounded recovery. The current configured snapshot command
   can return normally for a partial audit. Inspect persisted audit/manifest
   stages, required source availability, page/inspection errors and coverage
   rather than treating exit code zero, one good page or Google data alone as
   complete. Distinguish collection completeness from actual indexing/SEO health.
   Preserve usable independent sources when another fails. Detect challenged or
   unfinished responses, including challenge HTML with an apparently successful
   status, without labeling them page content, noindex, deletion or outside edits.
   Respect robots, host/public-DNS/peer boundaries, TLS, redirects, sizes and
   request/rate budgets. Keep the honest crawler identity; no CAPTCHA bypass,
   impersonation, browser cookies or credential replay.
   Bound Google requests and whole-job runtime so a hung network call cannot
   occupy the weekly worker indefinitely. Use a small capped retry policy with
   backoff for temporary network/quota/hosting failures; honor Retry-After where
   appropriate. Access revocation, unsafe destinations and invalid storage are
   actionable stops, not infinite retries. Do not hammer challenges or change
   SiteGround security settings.

5. Unattended Google readiness. Test normal expired-token refresh and secure
   persistence with mocked credentials, including scope changes, Vault payload
   overflow/write failure and revoked refresh tokens. There is no plaintext
   fallback or silent account replacement. The October 9 live readiness check
   refreshed the selected connection only in memory and preserved its saved
   payload; that does not prove scheduled-context persistence or long-term access.
   Verify the OAuth application's publishing status read-only during coordinated
   live setup. External apps in Testing can issue seven-day refresh tokens; do
   not assume a token refreshed today will work indefinitely. Preserve the exact
   https://www.googleapis.com/auth/webmasters.readonly scope. Prepare any needed
   Google configuration/reconnection action with its reason and obtain the user's
   exact authorization before changing it. Never replace the existing connection
   merely to test scheduling. Explain invalid/revoked access with a precise
   reconnect action and keep independent sites/connections unaffected.

6. Windows integration and app controls. Provide a reviewed registration/update/
   disable/remove interface for only this app's identifiable scheduled task, with
   a preview of executable, arguments, working directory, Windows principal,
   trigger/timezone, retry/timeout/power settings and rollback. Use absolute paths
   to the stable primary .venv-mvp Python/worker and protected configuration;
   do not leave production pointing at a disposable development worktree. Launch
   without a visible console and without storing a Windows password or requesting
   administrator/SYSTEM execution just for convenience. Verify Vault access under
   the actual chosen Windows user/logon context. If the first implementation
   requires that user to remain signed in, say so; a locked desktop, signed-out
   machine, sleeping machine and powered-off machine are different conditions.
   Support missed-run catch-up and avoid changing machine power policy. Do not
   promise collection while this computer is unavailable; show overdue state and
   explain when a dedicated always-on host would be necessary.
   Show schedule enabled/disabled, next run, last attempt/complete audit, retry,
   overdue and failure reason in the app, with Run now and disable controls.
   Keep the interface understandable to the user and their wife. Provide local
   actionable failure/completion status; no email/Slack messages or separate
   notification service under this prompt. App reruns must not register tasks or
   launch requests repeatedly. Backup/restore retains appropriate schedule history
   but must not automatically enable a restored schedule on another installation.

Validate with synthetic fixtures: timezone/DST, restart/catch-up, duplicate
triggers, partial/failed/unavailable stages, challenge responses, bounded retries,
interrupted jobs, lock contention across processes, expired/revoked/oversized
credentials, task-path quoting (including spaces), wrong workspace/installation,
site isolation, migration and backup/restore. Mock Task Scheduler mutations for
tests; do not install a live task as a unit-test side effect. Run focused and full
tests, AppTest and a separate synthetic real-browser smoke test for UI changes,
dependency consistency and whitespace checks. Cite actual results and limits.

Commit/push only validated public source/docs, create and attach a PR, and merge
to current main as the user requested, without force-pushing. Keep private data,
task-specific IDs, raw logs, credentials and backups ignored. Integrate one branch
at a time. Do not restart or migrate the primary app without verifying idle state,
preserving a protected rollback backup and coordinating release of the primary
workspace by the SEO task. Do not stop another task's processes.

After integration, prepare the concrete enablement packet and exact disable/remove
rollback. During parallel SEO work leave the live schedule disabled. Once the user
releases the primary workspace and chooses/enables the reviewed schedule, perform
one bounded ordinary headless live audit from the primary installation under the
actual scheduled principal. Verify it appears in history with honest stage status;
the October 9 audit used temporary in-process capture/credential/timeout adapters
and is not proof of this normal scheduled execution path. No browser sign-in should
be required for website fetching. Verify task registration/status and the next due
time without repeatedly running live audits. If activation/access cannot be
verified, preserve the completed implementation and give one exact remaining
setup step; do not claim weekly automation is active.

The deliverable is working, tested scheduling support, clear operational docs and
a reviewable activation path, with actual registration/live status reported.
No website publishing, indexing requests, sitemap/property writes, hosting changes,
permission changes, cloud migration or broader OAuth access is authorized here.
```

## References to verify during implementation

- [Windows Task Scheduler and missed-run catch-up](https://learn.microsoft.com/en-us/windows/win32/taskschd/about-the-task-scheduler)
- [Google OAuth refresh-token lifetime and Testing status](https://developers.google.com/identity/protocols/oauth2)
- [Protected local storage](local-storage-policy.md)
- [Current tracking operations](automatic-change-tracking.md)
