# Build automatic change tracking and annotated SEO trends

Recommended setup: **GPT-6.1 Sol** (`gpt-6.1-sol`), **High** effort (`high`).
Choose those settings in the task composer before sending the prompt. Sol is
documented for complex coding/professional work; High is a practical starting point
for state transitions, reporting correctness and isolation checks. This recommendation
has not been benchmarked against other models.
[Official model](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[effort guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Copy the block below into a separate task for this repository. Start it in an
isolated worktree from current main. This prompt does not ask you to start another
task or spawn subagents.

## Copyable prompt

```text
Build the next focused local SEO app feature: automatic website change history
and SEO trend charts with updates marked on them. The user approved the workflow
in docs/seo-change-workflow.md. Carry out the implementation, not just a plan.

Read AGENTS.md, README.md, docs/seo-change-workflow.md,
docs/guided-setup-and-learning.md, docs/website-change-policy.md,
docs/local-storage-policy.md and docs/local-preview-format.md. Inspect the existing
app, storage, learning, runner, public fetcher, Google exports, backups and tests.
The prior validation baseline is 97 tests at main commit 8802cbf, not proof of your
new changes. Historical follow-up prompts retain old limitations and scope; the
current workflow extends local tracking scope without authorizing CMS writes.

Use a separate worktree/branch based on current main. Reuse a suitable attached
worktree or create one for this task. Development uses isolated synthetic data
and a different available loopback port. Do not open/migrate the primary private
database, access real credentials, run live audits, stop/restart the user's app
on port 8502 or copy ignored private assets into your worktree. A second task is
continuing Meadow & Mind's audit in the primary protected workspace.

Implement these pieces together:

1. Extend the existing journal with persistent, site/action/revision-scoped
   implementation attempts, outcomes, verification and corrections. Preserve old
   plans/change events/reviews; use an additive, tested migration and old/new
   backup restore support. Distinguish local/staging, approved, attempted,
   reported applied, observed publicly, failed/partial, rolled back and measured.
   Do not collapse approval, publication, verification and SEO outcome into one
   status. No automatic rule tuning or cross-site learning.

2. Provide a documented local API/CLI for an authorized execution agent to record
   implementation receipts without duplicate manual entry. Bind receipts to exact
   actions and proposal revisions; preserve current/proposed/actual values,
   approval references, timestamps and verification sources. Reject cross-site
   relationships, duplicate/replayed submissions, invalid timestamps and
   contradictory transitions. Preserve failed and partially completed batches.
   A receipt reports work; it cannot execute website changes or grant approval.

3. Add a clear review of a frozen exact publication batch in the app, with values,
   confirmations, validation and rollback. Record approval only from explicit
   human authorization; an imported string, another agent, a reviewed state or a
   tracking plan is not permission. Bind approval to the exact revision/action
   set. Any changed proposal or stale current value must invalidate reuse for the
   affected action. Keep publishing unavailable: do not add a WordPress writer,
   broad credentials, deployment integration or in-app AI provider. Until execution
   is connected, explain the separate authorized WordPress implementation step.

4. Add bounded read-only comparison of tracked public pages to detect outside
   edits, using the reviewed public fetcher and explicit site context. Preserve
   source snapshots and exact meaningful diffs, with conservative normalization
   for genuinely dynamic content. Track selected title/headings/copy/links and
   technical values when available; a whole-page hash alone is insufficient.
   Mark outside edits first observed with an uncertainty interval and unknown
   author/publication time. Do not attach them automatically to matching plans,
   invent approval or treat HTTP 202/challenges/errors as content/deletion evidence.
   Keep incomplete sources visible and do not weaken robots/TLS/destination checks.

5. Integrate persistent whole-site and tracked-page trend charts with readable
   change markers. Clicking/selecting a marker shows exact before/after, rationale,
   expectation, evidence, approval reference, verification and saved reviews.
   Add bounded finalized daily page exports; current daily exports are whole-site
   only. Preserve byProperty versus byPage, Pacific reporting dates, weighted
   position and CTR math. Resolve overlapping-audit dates with explicit provenance
   rather than adding duplicate rows. Preserve prior evidence and show collection
   gaps/unknown values. Do not infer qualified inquiries or map-pack rank.
   Retain the journal's equal complete before/after comparisons and no-causality
   limits; uncertain observation dates cannot establish a precise change date.

6. Automate throttled read-only checks on explicit site opening and audit
   completion, with a manual Refresh control, last-checked times, bounded settings,
   progress/errors and no requests duplicated by Streamlit reruns. Coordinate
   check/audit/backup concurrency. A closed app is not monitoring: do not install
   a background service, scheduler or notification system in this task.

7. Consume the versioned proposal handoff in docs/seo-change-workflow.md with a
   strict inert validator and idempotent import. Keep it usable with existing
   plans/preview actions while the parallel audit task prepares new evidence.
   Include new receipts/snapshots/exports in safe backups and source-scoped packets
   without credentials. Protect private writes, exports and browser rendering.

Keep the Search Console scope exactly
https://www.googleapis.com/auth/webmasters.readonly. Do not request indexing,
alter properties/sitemaps or broaden OAuth access. Encryption is optional;
restricted Windows folders and fresh write gates remain mandatory. Do not cache
protection across reruns, change machine permissions, upload private evidence,
invent business/clinical facts or enable a live feature when prerequisites fail.

Use synthetic fixtures to test receipts, replay/partial failure, site/revision
isolation, human approval versus imported claims, outside-change intervals,
unavailable/challenged fetches, conservative diffs, overlapping time-series dates,
metric math, source gaps, historical immutability, concurrency, restart persistence,
safe rendering/CSV export and old/new backup restore. Run focused tests and the
full suite after material changes, plus AppTest and a real browser smoke check.
Document what was actually validated. Do not use the real practice to prove tests.

Own tracking app/storage/learning/exports and related tests/docs. The other task
owns read-only practice diagnosis, evidence and crawler-specific fixes. Report
an unavoidable overlap before editing it. Worktree locks are checkout-local;
never run this development checkout against the primary private workspace.

Commit and push validated source/docs, create and attach a PR, then merge to main
as the user requested, integrating against current main without force-pushing.
Never publish private files. Keep primary app/database rollout separate until
the audit task's live jobs are idle and protected backup/migration checks pass.
Finish with working usage instructions, actual test/browser results, remaining
execution prerequisites and an honest distinction between synthetic validation
and verified live behavior. If live access is unavailable, finish independent
local work and give the user one precise next step in plain language.
```
