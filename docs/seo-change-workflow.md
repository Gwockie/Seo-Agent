# Website changes, trends and learning

Agreed workflow, October 8, 2026. This document describes the next implementation;
it does not claim that the features below already exist or authorize publication.

The user wants to review recommendations with their wife in the app, approve exact
published changes, and see subsequent SEO trends alongside a reliable history of
what changed. Routine recording should happen automatically during implementation.
The goal is to learn from evidence without making the user enter the same facts twice.

## What exists and what needs building

| Capability | Current state |
| --- | --- |
| Independent site setup, protected local evidence and read-only Google account | Implemented |
| Historical audits and static before/after page previews | Implemented; previews are local copies |
| Recommendation rationale, expected effects and measurement plans | Implemented |
| Saved plans, user-reported implementation records and append-only result reviews | Implemented |
| Whole-site daily trends and selected before/after comparisons | Implemented; change markers are not integrated |
| Automatic implementation receipts and recognition of outside edits | To build |
| Persistent charts connecting site/page trends to specific updates | To build; page-specific daily exports also need adding |
| Approval of a frozen exact batch through the app | To build; currently obtain explicit human approval in the conversation |
| WordPress publishing connection or unattended background collection | Not implemented; outside this tracking build |

The last application validation passed 97 tests, including 14 Streamlit AppTest
scenarios, at main commit `8802cbf9415fc258fd737507afe8b667f151530a` (PR #6).
That is a dated baseline, not verification of these planned features.

## End-to-end use

1. **Collect a baseline.** Preserve the selected site's profile, rules, public-page
   evidence and Google metrics. Display each source's completeness independently.
   The original practice currently has useful Google evidence and a partial crawl.
2. **Prepare recommendations.** Each action identifies the exact page/setting,
   current and proposed values, supporting evidence, reason, expected effect,
   factual confirmations, validation, rollback and intended measurement.
3. **Review together.** In Recommendations & changes, compare Before and Proposed
   with highlights. Revise local drafts freely. Clinical claims need the clinician's
   confirmation. The original practice has no hosted staging; these previews save
   nothing to WordPress. Verified isolated staging can be revised under the standing
   authorization in [the change policy](website-change-policy.md).
4. **Approve an exact publication batch.** Refresh the current public values and
   select the exact actions. Human approval must bind the site, URLs, values and
   proposal revision. A changed proposal or mismatched current value requires a new
   review of the affected action. Review state and imported approval claims are not
   authorization. Until the approval UI exists, obtain permission in the conversation.
5. **Implement and verify.** A human or an agent with separately authorized WordPress
   access applies only the approved actions. Preserve an implementation receipt and
   verify the rendered public values and relevant behavior. Record failures and
   partial completion, rather than assuming every approved action was applied.
6. **Measure.** Collect later finalized Google data and chart it with change markers.
   Examine the affected page and relevant queries as well as whole-site trends.
   A useful chart can appear before a sufficiently long comparison exists; label
   evidence that is too early, incomplete, unavailable or inconclusive.
7. **Learn.** Save observations, uncertainty and other plausible explanations.
   The selected site's history informs its next recommendations. Updating trusted
   rules or sharing a general lesson requires separate review and applicability
   checks; there is no automatic cross-site learning or model training.

## Automatic recording and outside changes

For an approved agent implementation, expose a validated local receipt API/CLI so
the execution workflow can record attempts and outcomes without retyping them in
the UI. A receipt records actual actions; it does not perform a website write or
grant approval. Bind it to exact site/action/revision identities and reject replay,
cross-site references and contradictory values. Keep corrections append-only.

Distinguish these facts: proposed, approved, attempted, reported applied, observed
publicly, rolled back, and measured. Public verification of a value does not prove
the edit was authorized or the exact time it was published. Do not silently turn an
outside edit into an approved implementation or attach it to a matching draft.

For direct WordPress edits, bounded read-only checks compare successful snapshots
of selected tracked pages with prior successful snapshots. Track meaningful title,
heading, copy, link, canonical and index-directive changes; do not treat dynamic
timestamps or a page-wide hash as an exact actionable diff. Preserve original
captures alongside any normalization. Failed, challenged, incomplete or redirected
responses cannot be treated as page deletions or changes to the actual content.

Outside changes carry a last-known-before and first-observed-after interval, with
unknown author/publication time unless independent evidence supplies it. Keep
reported implementation time, observation time, source and verification separate.
Historic October 6 fixes remain user-reported and unspecified until evidence
identifies their exact actions. Local/staging edits get no live performance marker.

## Charts and evidence

Provide a site-scoped timeline and charts with selectable page/metric, readable
change markers and an action detail view containing before/after, why, expectation,
approval reference, verification and outcome reviews. Start with impressions, clicks,
CTR and position. Qualified inquiries and map-pack rank need other evidence and
must not be invented or inferred from clicks/average organic position.

Use daily page data for page trends, not whole-site totals labeled as a page result.
Google supports date/page/query dimensions and finalized data in its
[Search Analytics API](https://developers.google.com/webmaster-tools/v1/searchanalytics/query).
Keep byProperty and byPage datasets separate. Compute CTR from summed clicks and
impressions, and position with impression weighting within one consistent dataset.
Keep reporting dates in Pacific time and capture/receipt timestamps in UTC.

Deduplicate dates from overlapping audits without summing the same observations.
Preserve the chosen source/version and prior exports. Represent unavailable rows
and collection gaps explicitly; do not manufacture zero values or connect a trend
line across an unknown gap. Show limits from query privacy/top-row exports.

Before/after comparisons require finalized compatible data, equal complete windows
strictly before and after the actual change date, and consistent target/brand
definitions. An uncertain observation interval must not become a precise publication
date. Show other changes in the period. Wording such as "clicks increased after this
update" is an observation; "this update caused the increase" needs evidence the app
does not currently collect. Small samples may remain inconclusive.

## Local operation and safety

The first build may perform bounded, throttled read-only refreshes when an explicitly
selected site opens and when an audit completes, with a manual Refresh control,
last-checked time and visible source failures. Streamlit reruns must not duplicate
requests or delay every widget interaction. Coordinate audit/check/backup jobs.
An app that is closed is not monitoring the website. Installing a scheduler/service,
sending notifications or adding hosted monitoring is a separate decision.

Retain protected Windows folders, Windows Vault credentials, loopback/CORS/XSRF
protections, safe public fetching, inert previews and formula-safe exports. Encryption
remains optional. Never put credentials in receipts, charts, logs or backups.
Search Console's only scope remains `webmasters.readonly`; this workflow neither
submits indexing requests nor changes sitemaps/properties. Publication requires the
exact permission in [AGENTS.md](../AGENTS.md) and the change policy.

## Running the next two tasks in parallel

Use the [tracking build prompt](change-tracking-agent-prompt.md) and the
[Meadow & Mind audit prompt](meadow-and-mind-agent-prompt.md) in separate tasks.
Set both to GPT-6.1 Sol, High effort. The model is documented for complex coding
and professional work; High suits tracing logic and edge cases. This is a task
recommendation, not a measured comparison with other models.
[Model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[effort guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents).

| Task | Owns | Avoids |
| --- | --- | --- |
| Tracking build | Separate worktree, synthetic fixtures, app/storage/receipt/chart changes and tests | Production database, real account credentials, live audit jobs and app on port 8502 |
| Meadow & Mind | Primary protected evidence, read-only diagnostics, new audits, reviewed reports and local proposal revisions | Tracking modules/schema/UI; any publication without later exact approval |

Worktrees do not copy ignored workspaces, credentials or historical evidence. The
current audit lock is scoped to a checkout, not all worktrees. Only the Meadow & Mind
task uses the primary live workspace/launcher. A needed crawler source fix belongs
in a separate branch/worktree and must avoid tracking-owned files. If an overlap is
necessary, report the exact file/interface and coordinate before editing it.

Commit/push validated public source/docs and merge to main as the user requested;
keep all private evidence out of Git. Integrate one branch at a time against current
main. Primary app restart or database migration waits until no live audit, backup
or collection job is active. Do not stop another task's server/process.

The audit task can proceed without the new receipt code. It uses existing saved
plans/preview actions and adds a new Markdown handoff in the selected audit's
protected reports directory. Markdown handoffs are covered by existing backup and
report-packet rules. Preserve older handoffs; use a generated ID in the filename.

The handoff contains a fenced JSON object with `schema: "seo-change-handoff/1"`,
`kind: "proposal"`, selected `site_id`, `audit_id`, UTC preparation time and an
`actions` list. Each action has a stable generated `action_id`, exact URL and action
kind, current/proposed values, capture time/source, rationale, expected effect,
primary measure, measurement method, factual confirmations, validation, rollback
and own-audit evidence references. References identify file/row or capture revision
and node where available. Unconfirmed facts and unavailable current values are
explicit. There is no approval, implementation or performance-outcome assertion.

Use these field names so the two tasks can work independently:

| Object | Required fields and types |
| --- | --- |
| Root | `schema` and `kind` as above; `site_id` and `audit_id` as existing generated IDs; `prepared_utc` as an ISO UTC timestamp; `actions` as a bounded list |
| Action identity/value | `action_id` as a new stable generated ID; `url` as an exact selected-site URL; `action_kind` as `title`, `text`, `href`, `canonical`, `index_directive` or `setting`; `current` as literal text or null when unavailable; `proposed` as literal text |
| Action explanation | Nonempty strings: `current_source`, `rationale`, `expected_effect`, `measurement`, `validation`, `rollback`; `capture_time_utc` as an ISO UTC timestamp or null; `primary_measure` as one of the existing journal's `METRICS` labels |
| Action confirmations | `confirmations` as a list of objects with `item`, `status` (`pending` or `confirmed`) and `source` (text or null); a claimed confirmation remains a supplied assertion needing review |
| Action evidence | `evidence` as a list of objects with own-audit relative `file` and nullable `row`, `revision`, `node_id`; CSV rows count the header as row 1 |

Missing current values, capture times or confirmations make publication readiness
incomplete; the handoff must still be useful for planning. Evidence references must
resolve through checked site/audit paths, never arbitrary absolute/traversal paths.
Do not add an approval flag or use a schema-valid proposal as authority to publish.

The tracking task validates this contract, preserves its provenance and prevents
duplicate import; untrusted handoff text never becomes executable instructions or
publication permission. New complete audits and this handoff are the integration
point. Neither task needs another client's data or credentials to proceed.
