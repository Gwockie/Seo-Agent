# Automatic change history and annotated trends

This implementation is local and read-only toward websites and Google. It adds
an additive SQLite version 2 migration. Opening an old workspace creates tracking
tables without rewriting its plans, implementation observations, reviews or audit
files. Do not open the primary workspace from a development checkout.

## Use in the app

1. Select the site and audit explicitly. In **Recommendations & changes**, import
   the versioned proposal handoff described in `seo-change-workflow.md`, or select
   **Track these saved preview actions**. Existing plans can be extended from
   **Changes & results**. These operations create proposals, never approval.
2. In **Changes & results**, review tracked URLs and bounds. The default is six
   pages and a six-hour minimum automatic interval. Additional exact site URLs,
   latest proposal pages and configured target landing pages are included, in
   that order, up to the page limit. Use **Refresh tracked pages** for a current
   public capture. Manual requests have a 15-second debounce.
3. Review each action's literal current/proposed values, reason, expectation,
   evidence, confirmations, validation and rollback. Append a revision to correct
   a proposal; prior revisions remain available in frozen batches and history.
   Missing current values/capture times remain useful for planning. Adopt a fresh
   successful public capture and confirm factual items with the owner/clinician
   before requesting publication review. Text/link actions need an exact target in
   saved preview evidence. The frozen packet binds its structural path, sibling/
   child layout, text-child slot when applicable, full before/after content and
   link label. A matching value elsewhere cannot validate approval or verification.
   If browser-captured structure differs from static HTML, capture a new matching
   preview; do not guess the target. Unresolved targets and settings remain unready.
4. Select exact actions and **Freeze selected publication batch**. Current public
   values must match uniquely, captures must be at most 24 hours old, and factual
   assertions must be complete. Overlapping actions are rejected. The frozen
   values, action set, revisions and fingerprint do not change.
5. The human reviews that frozen packet, checks the review statement, names the
   factual confirmation source, types **I approve this exact publication batch**
   and submits **Record my exact human approval**. Reading a report, marking a
   recommendation reviewed, importing a confirmation assertion, or entering an
   approval reference elsewhere does not authorize publication.
6. A separately authorized human/agent implements only those exact actions in
   WordPress. This app has no CMS writer, deployment integration or AI provider.
   Record an attempt immediately **before** the website action, then its outcome
   through the receipt interface below. A receipt itself cannot execute work or
   grant approval. The execution workflow must also satisfy the website policy.
7. Refresh and inspect public values. An explicit receipt may reference a saved
   successful public snapshot for verification. This establishes an observed
   value, not the author or exact publication time. The outside-edit record stays
   independent; it is never automatically attached to a matching proposal.
8. In **Changes & results**, select whole-site/page scope and impressions, clicks,
   CTR or position. Select a change marker to see values, rationale/expectation
   when known, evidence, approval reference, verification and saved reviews.
   Exact-action evidence reviews append and preserve their comparison results.

The facts remain separate: proposed revision, frozen batch, human approval,
attempt, reported applied/failed/partial work, public observation, rollback,
correction and measurement review. Local/staging receipts have no live marker.
A failed action does not erase other attempted or completed actions in its batch.
Unspecified October 6 fixes remain legacy user-reported observations.

Changed revisions cannot reuse approval. Once a successful public comparison
finds a stale current value, an append-only invalidation prevents the affected
action's approval from becoming usable again even if that value later returns.
Reported partial work, corrections and rollbacks require renewed review before
another production attempt. Unaffected actions keep their exact approved scope.
Earlier frozen text/link batches without target bindings remain historical but
cannot authorize new work. Freeze a fresh batch after reviewing captured targets.

## Local agent CLI and Python interface

Use the protected **selected workspace**, site and audit. Input files containing
private evidence need a protected folder too. Commands use the audit/check/backup
lock. They do not load Google credentials or write to a website.

```powershell
python -m seo_agent --workspace WORKSPACE import-handoff --site-id SITE_ID --audit-id AUDIT_ID proposal.md
python -m seo_agent --workspace WORKSPACE record-receipt --site-id SITE_ID receipt.json
python -m seo_agent --workspace WORKSPACE tracking-refresh --site-id SITE_ID
```

Replace uppercase placeholders with the existing paths/generated IDs. Handoffs
accept JSON or one fenced `json` object in Markdown, up to 2 MiB/100 actions. The
strict `seo-change-handoff/1` contract rejects unknown fields, approval claims,
duplicate JSON keys, cross-site/audit references, traversal, missing evidence
files/rows/nodes, non-UTC/future timestamps and duplicate action IDs. Identical
validated imports return the original import ID. Different proposals reusing an
action ID need an explicit new revision instead of overwriting history. Supplied
confirmed facts are assertions for human review, not authorization.

Receipt JSON contract (`seo-implementation-receipt/1`):

| Field | Meaning |
| --- | --- |
| `schema` | Exactly `seo-implementation-receipt/1` |
| `receipt_id` | New generated 32-character lowercase hex ID, unique per event |
| `site_id`, `action_id`, `revision` | Exact saved site/action/revision; revision is an integer |
| `attempt_id` | New generated ID for an attempt; reuse only for its subsequent events |
| `environment` | `local`, `staging` or `production` |
| `outcome` | `attempted`, `reported_applied`, `failed`, `partial`, `rolled_back`, `verification` or `correction` |
| `occurred_utc` | ISO UTC timestamp, not future, not before proposal/approval/prior event |
| `current`, `proposed` | Literal saved values; current may be null if unknown |
| `actual` | Null for `attempted`; exact actual value for applied/partial/rollback |
| `approval_id` | Exact app-recorded human approval ID for production; null for local/staging |
| `source` | Nonempty execution log/reference, up to 4,000 characters |
| `verification` | Evidence text, up to 4,000 characters; empty when not verified |
| `verification_snapshot_id` | Optional successful own-site/page snapshot ID for explicit public verification |
| `corrects` | Prior outcome receipt ID in this same attempt for `correction`; otherwise null |

First submit `attempted` with `actual: null`. Then submit an outcome with a new
`receipt_id` and the same attempt/environment/approval/action/revision. An exact
applied value must equal the proposal; a different value is partial. A rollback
must report the original value. Terminal outcomes cannot be replaced: append an
explicit correction or start a new eligible attempt. A corrected receipt never
changes the earlier receipt. IDs and repeated identical events are replay checked.
Public verification snapshots must match the exact actual/proposed value, follow
the attempt and precede the verification receipt. A free-text verification source
alone is reported evidence, not independently verified public content.
`failed` may report an unknown actual value or the unchanged original value.
Any known changed value must be reported as `partial`, which invalidates approval
for that action. Contradictory changed failures saved by an earlier app version
also prevent approval reuse without rewriting their history.

For an execution agent calling Python directly:

```python
from pathlib import Path
from seo_agent.storage import Store
from seo_agent.tracking import import_handoff, record_receipt

store = Store(Path("WORKSPACE"), enforce_protection=True)
import_id = import_handoff(store, "SITE_ID", "AUDIT_ID", proposal_bytes)
receipt_id = record_receipt(store, "SITE_ID", receipt_dict_or_bytes)
```

The API applies the same inert validation and fresh private write gates. Local
same-user Python/database access is not an independent authentication boundary.
There is deliberately no approval CLI/import route. Only the human UI submission
handler calls the approval function. Do not automate that handler for real sites.
Never put passwords, tokens, OAuth JSON or patient/customer data in input fields.

## Public sources, dates and limits

Checks use the existing public GET-only fetcher without changing crawler code.
Robots, public DNS/socket destination checks, TLS, redirect boundaries, response
size and request limits remain in force. Up to 20 pages, eight-second response
budgets and a 90-second between-page overall budget bound each check (a request
already in progress can finish after that overall budget). No challenge solving,
credentials or ambient proxies are used. HTTP 202, errors, redirects, incomplete
HTML and challenges are unavailable, never content/deletion evidence. Failed
sources remain visible and preserve the last successful baseline.

Successful captures retain raw HTML as inert private source data and extracted
title, ordered headings/text/link values, canonical, meta index directives and
X-Robots-Tag. Only whitespace and active/nonvisible markup are normalized; dates,
prices and meaningful numbers are preserved. Static HTML does not establish
JavaScript-rendered content, CSS visibility or CMS settings. Raw HTML is never
rendered into the browser. Outside edits preserve exact field differences and
last-known-before/first-observed-after UTC intervals, with unknown author and
publication time. They cannot supply a precise date for before/after attribution.

Audit completion always imports immutable finalized daily sources. Opening the
selected site and completing an audit may trigger a throttled public check; a
manual refresh is also available. Persistent throttle records and one shared
process worker/workspace-scoped file lock prevent reruns and concurrent audit/check/backup jobs
from issuing duplicate collections. Interrupted checks retain their running record
and can be retried after the throttle; no result is invented. Errors preserve
prior evidence and appear in check history. Opening the app installs no service, task or notifications. Public tracking alone
needs an open app; separately reviewed [weekly audits](weekly-audits.md) can invoke
bounded tracking after collection while Streamlit is closed.

`gsc_daily.csv` remains whole-site **byProperty**. New bounded
`gsc_daily_pages.csv` exports date/page **byPage**, final web search, at most 50,000
top rows. Old audits lacking page daily exports cannot supply page trends.
Dates are Pacific reporting dates displayed on a UTC calendar scale; receipts and
captures use UTC instants. CTR uses clicks/impressions, position stays weighted
within the matching dataset, and property/page datasets are never combined.
For overlapping days, choose the newest complete saved collection, prefer current
over previous within that collection, and retain its audit/source ID and digest.
No duplicated date is summed. Absent rows and failed collections remain unknown;
chart lines break at gaps. Exports retain source-selection provenance.

The existing equal complete before/after journal checks remain. Exact-action
reviews require one reported production implementation and compatible, equal
finalized windows strictly before/after its Pacific date, with frozen baseline
brand/target definitions. Partial/corrected/rolled-back work and observation
intervals cannot establish that date. Other markers, demand, competition and
query privacy/top-row limits remain possible explanations. No causal effect,
qualified inquiries or map-pack rank is inferred; no rule tuning or cross-site
learning is added.

## Backups, exports and rollout

Credential-free backups include all new tracking tables/source captures and the
known page daily exports. Restore accepts the original pre-journal schema, the
version 1 journal and complete version 2 schema, validates table structures and
inert relationships, and adds empty tracking tables for old backups. Google
selections remain detached. Restored approvals are preserved as history only.
Receipt IDs, site IDs, action IDs and revisions must agree between SQLite columns
and their JSON payloads, and frozen target bindings must agree with source evidence.
Freeze a new batch and get fresh human approval before another production attempt.
Selected-audit ZIP packets include a `tracking.json` supplement with only that
audit's actions and related receipt, approval-history, observation/source and trend
records. Unassigned site-opening captures are included only when referenced by
that audit's tracked actions/batches/observations. CSV export escapes formulas.

Restricted Windows folders and fresh ACL/reparse checks remain mandatory for
private writes, exports and live collection. Encryption is optional. Google scope
remains exactly `https://www.googleapis.com/auth/webmasters.readonly`. No indexing,
sitemap/property changes or broader permissions are supported.

Source merge is separate from primary rollout. When the live audit/collection/
backup jobs are idle, create and verify a protected backup with the old app before
opening its workspace using the new app. Keep the old backup for rollback; rolling
back source alone does not downgrade a version 2 database. Restore the old backup
into a new protected directory if rollback is required. This build never opens,
migrates or restarts the primary app/database, and never uses the primary port 8502.

See `tracking-validation.md` for the checks actually performed. Synthetic tests
do not certify live WordPress, Google access or the primary rollout.
