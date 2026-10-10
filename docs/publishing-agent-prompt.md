# Publishing exact approved changes

Prepared October 10, 2026. Recommended implementation agent: **GPT-6 Astra,
High effort** for CMS mapping, approval enforcement and failure recovery. This is
a task-fit recommendation, not a repository benchmark.
[Official model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).

Start with a narrow deterministic WordPress adapter consuming exact human-approved
actions. Map each proposal to its real CMS field and detect stale values before
writing. Implement after the [revision/evaluation workflow](recommendation-editing-agent-prompt.md).
The app currently has no CMS writer; this brief does not activate publication.

## Copyable agent prompt

```text
Implement an application-controlled WordPress publishing workflow for exact,
human-approved website changes.

Repository: C:\Personal Projects\seo-agent\local-seo-agent

Read AGENTS.md, docs/website-change-policy.md, and docs/approval-to-publication.md.
Inspect exact actions, proposal revisions, frozen approval batches, factual
confirmations, publication receipts, workspace coordination and backup/restore.

User outcome: A user reviews a concrete publication batch, explicitly approves
its exact actions, and instructs the app to apply them to the selected website.
The app records and verifies what happened.

Begin with a narrow, fully implemented set of supported changes. Discover the
actual CMS/editor/SEO-plugin structure through read-only inspection and current
official documentation. Do not assume a public HTML selector maps to a writable
WordPress field.

Use a deterministic CMS adapter consuming frozen approved actions. Map each
action to an explicit site, URL, CMS object and field/block/widget identifier.
Distinguish page/post titles, visible headings, SEO titles and shared templates.
Reject ambiguous mappings, unsupported actions and unintended shared effects.
Preserve unrelated CMS content and metadata.

Provide publication review showing affected URLs/fields, current and proposed
values, factual confirmations, validation, intended writes and rollback actions.
Human approval must cover the exact revision and enumerated actions.

Before a production write, verify the destination, selected site, frozen batch,
approval, required confirmations and current validation. Read fresh CMS values;
stop on conflicts or stale approval. Show the precise write scope, including
any autosave/draft behavior. Prevent races using the CMS's supported mechanisms;
do not assume it provides atomic compare-and-write or version locks.

Editing proposed wording must invalidate affected publication authorization.
Models, scheduled audits, review jobs and imports cannot create human approval.
Historical receipts must not authorize publication again. Agent-controlled UI or
API paths must not impersonate the human approval ceremony.

Use separate protected CMS credentials with minimum necessary permissions.
Keep secrets out of logs, exports, repository files and ordinary database records.
Preserve Search Console's read-only scope. Restrict authenticated requests to the
configured verified destination. Keep publishing disabled until a human configures
the destination and credentials.

Implement durable attempt tracking and duplicate-submission protection. Handle
concurrent edits, interrupted requests, uncertain timeouts and partial failures.
Reconcile uncertain outcomes by reading the destination before retrying. Do not
assume multi-action batches are atomic.

Capture before-values and per-action results. Verify approved CMS fields and public
output after writing, including relevant adjacent content and technical directives.
Report write success separately from verification success.

Provide rollback using captured values and fresh conflict checks. Production
rollback needs exact human authorization, explicitly included in the reviewed
batch or obtained separately. Never silently overwrite later human edits.

Backup restoration must not silently re-enable publishing, restore active
credentials or make old approvals reusable.

Support verified isolated staging where available. This implementation task does
not authorize production writes or production draft/autosave changes. Use synthetic
fixtures and a local/test WordPress environment for writes. If hosted staging
isolation is unknown, continue locally.

Test wrong-site targeting, stale approvals, unsupported fields, CMS conflicts,
duplicate clicks, timeouts, partial success, verification failure and rollback
conflicts. Preserve read-only auditing and review scheduling.

Deliver a working adapter, approval/publication UI, receipts, tests, setup docs,
and a reviewable pull request. Document supported CMS/editor combinations and
unsupported actions. Include a concrete plan for separately approved live validation.

Do not publish to real production, install production plugins, alter DNS, or
enable automatic publication as part of this task.
```
