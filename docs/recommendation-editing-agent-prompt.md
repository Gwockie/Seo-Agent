# Editable recommendations and revision evaluation

Prepared October 10, 2026. Recommended implementation agent: **GPT-6.1 Sol,
High effort**. This is a task-fit recommendation, not a repository benchmark.
[OpenAI model-selection guidance](https://developers.openai.com/api/docs/guides/model-selection).

The existing exact-action editor saves revisions. Extend that foundation into an
approachable edit, evaluate, revise and approve workflow. Prepublication evaluation
assesses expected usefulness; actual effectiveness requires later measurement.
Stylistic disagreements should produce advice, while factual and technical
blockers remain enforced. Implement this before the
[publishing integration](publishing-agent-prompt.md).

## Copyable agent prompt

```text
Implement an in-app workflow for editing SEO recommendations and evaluating the
revised proposal before approval.

Repository: C:\Personal Projects\seo-agent\local-seo-agent

Read AGENTS.md, docs/website-change-policy.md, and docs/approval-to-publication.md.
Inspect the current recommendation, exact-action, revision, factual-confirmation,
evaluation, and approval flows. Build on the existing editor and saved revisions.

User outcome: A user can open a recommendation, change its wording or proposed
action, optionally explain their disagreement, save a revision, and ask the app
to evaluate that specific revision. Editing must not approve, reject, or publish.

Requirements:
- Provide an understandable Edit/Revise action from the recommendation view.
- Support relevant proposal fields: proposed text, rationale, expected effect,
  and factual questions.
- Preserve original recommendations, evidence, and revision history. Show a
  clear comparison between versions.
- Keep editable proposals separate from observed current website values.
  Editing an observation must not make it verified evidence.
- Let users compare alternatives and restore an earlier version as a new revision.

Evaluate against the selected site's validated profile, goals, facts, saved rules,
audit evidence, and exact target. Assess query intent, service/local relevance,
clarity, factual support, and applicable technical constraints. Never import
another site's assumptions or invent clinical claims.

Present what the revision improves or weakens, supporting evidence, uncertainty,
missing factual confirmations, advisory suggestions versus mandatory blockers,
and a way to measure results after publication. Call this an assessment of
expected effectiveness. Do not guarantee rankings, invent numerical uplift, or
optimize for SEO-plugin scores.

Use deterministic checks for enforceable constraints. Reuse existing configured
review/model infrastructure where appropriate. Distinguish mechanical validation
from model judgment. If model review is unavailable, say so rather than presenting
mechanical checks as a complete effectiveness review. Respect existing privacy,
external-processing consent, configuration and execution limits.

Bind evaluations to the exact proposal revision and relevant evidence/configuration
version. Subsequent edits must make the affected evaluation and approval stale.
Preserve historical approved batches unchanged; revised wording needs new approval.

A model must never confirm owner-only facts, approve its own proposal, or publish.
Users may retain stylistic choices despite advisory feedback, but unresolved
mandatory factual or technical blockers must remain visible and enforced.

Maintain multi-site isolation, existing privacy controls, backup/restore behavior,
and human-owned exact-action approval.

Validate with synthetic fixtures and meaningful tests for revision history,
stale evaluations, stale approvals, factual blockers, advisory disagreement,
unavailable review infrastructure, and cross-site isolation. Demonstrate the UI.

Deliver the working feature, relevant documentation, tests, and a reviewable pull
request. Explain what the evaluator can establish and what needs later measurement.

This task authorizes application development and local testing. It does not
authorize production website changes, publishing, or enabling scheduled jobs.
```
