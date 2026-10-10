# Scheduled and threshold-triggered review generation

Prepared October 10, 2026. Paste the following prompt into a development agent.
This is an implementation brief, not an enabled automation or publication approval.

```text
Implement scheduled and threshold-triggered generation of useful private SEO
review packets in this repository. Carry the feature through validation, push a
reviewable PR, and merge it into current main after its checks pass. Do not activate
a live schedule, transmit private client evidence to an unapproved processor, or
edit/publish a website under this prompt.

Read AGENTS.md, README.md, docs/website-change-policy.md,
docs/local-storage-policy.md, docs/setup-and-migration.md,
docs/weekly-audits.md, docs/weekly-audit-validation.md,
docs/automatic-change-tracking.md, docs/tracking-validation.md,
docs/seo-change-workflow.md, docs/local-preview-format.md,
docs/review-in-app.md and docs/approval-to-publication.md. Inspect current main
and relevant source/tests; older planning prompts describe historical states.

Weekly auditing is already implemented in PR #11. It uses Windows Task Scheduler,
a durable bounded worker, independent per-site schedules and a workspace-scoped
coordination gate. Audits generate deterministic findings/basic reports, ingest
trends and check public pages. Exact proposals, frozen batches, human approval,
implementation receipts and static preview revisions also exist. The app has no
CMS writer or AI provider/executor. Build on these interfaces rather than adding
another competing scheduler or pretending that rule reports are agent reviews.

Use an isolated managed worktree based on current main. Inspect existing worktree
attachments before creating one. Develop only with synthetic protected fixtures;
never open/migrate the primary private database from development, copy ignored
credentials/evidence, or stop another chat's processes. Recheck ownership before
editing shared app/runner/storage/backup/scheduling files. Do not message other
chats without human authorization. Only the canonical primary installation may
run real jobs, after explicit rollout and idle/backup prerequisites are satisfied.

Deliver:

1. Independent per-site review-generation settings, disabled by default. Support
   periodic review after eligible audits, event/threshold mode, or both. Configure
   frequency, minimum spacing/cooldown, bounded pages/actions/runtime, and actual
   execution cost limits when a paid provider is involved. Expose preview of why
   a selected saved audit would or would not generate a review without launching
   collection or a model request. No unrelated site inherits these settings.

2. A deterministic eligibility evaluator. Structural triggers include newly
   observed priority-page indexing restrictions/canonical disagreement, verified
   broken internal destinations, new query/page alignment findings, and meaningful
   tracked public content changes. Preserve intentional exclusions, partial source
   status and uncertainty. A complete collection is not proof of indexing health.
   A failed/challenged fetch is never a deletion, noindex or content-change trigger.

   Performance triggers should have configurable minimum impressions, relative
   and absolute effect thresholds, comparable window length, and persistence over
   distinct eligible observations. Explain which baseline, metric and scope were
   evaluated. Repeated triggers on the same audit must not count as persistence;
   heavily overlapping reporting windows must not masquerade as independent
   confirmation. Use finalized web data/Pacific reporting dates, equal complete
   compatible windows, separate byProperty/byPage/query aggregations, weighted
   position and CTR from totals. Deduplicate daily provenance; missing query/page
   rows stay unknown. Use the existing rule settings where applicable. Percentage
   changes alone on small samples should not generate confident recommendations.
   These triggers are review leads, not proof of cause, Maps rank or inquiries.

3. Durable review jobs with an explicit site, immutable producing audit/config/rule
   versions, trigger evidence, baseline, status, attempt history and output IDs.
   Serialize short protected mutations through the existing workspace coordination
   gate. Do not hold collection locks throughout a slow model call; stage an
   immutable scoped input and revalidate source/revision state before importing
   output. Respect migration ordering, busy/deferred states, bounded retries,
   interruption recovery and cancellation. Restores preserve history and keep
   execution disabled until reconfigured.

   Deduplicate equivalent unresolved proposals using exact site/page/field/target,
   current/proposed content and producing evidence. Recheck changed facts/source
   values; supersede through append-only revisions, never delete history or carry
   old approval onto changed wording. Show no-change/skipped outcomes honestly.
   A timer alone must not produce a new packet with identical recommendations.

4. A real, explicit review executor boundary. Separate deterministic job creation
   from agent interpretation. Provide a manual/local agent handoff mode and an
   approved automatic executor adapter with capability checks. Select/configure
   its runtime/model/provider deliberately; do not invent a Codex API, rely on an
   interactive browser session, embed credentials in commands, or shell-execute
   crawled/model-generated instructions. Research supported official interfaces
   if needed. Local handoffs must not be described as unattended execution.

   Private evidence cannot be sent to model services merely because this feature
   exists. Automatic outbound execution remains unavailable until the user has
   approved the concrete processor/destination, minimum input fields, retention
   implications and spending bounds. An approved execution configuration can be
   reused within that scope; do not demand per-run approval unnecessarily. Never
   send Google tokens, secrets, patient data, another site's evidence or unrelated
   files. Store any provider credential through a reviewed protected mechanism;
   no plaintext fallback. Test an actual supported adapter using non-sensitive
   synthetic input before claiming automatic generation works. If required runtime
   access is missing, finish the queue/manual handoff path and show the precise
   unavailable state rather than marking the automatic path complete.

5. Agent-produced reviewed summary, prioritized recommendations, exact local edit
   proposals, before/proposed numbered preview revisions and review/publication
   packet. Use the repository seo-audit skill only for its intended read-only
   interpretation, after app-validating the selected site/profile/audit; use the
   psychology reference only for that saved profile. Saved goals, facts and rules
   govern interpretation. General sites must not receive psychology advice.

   Each recommendation needs own-audit row/capture/target evidence, dates and rule
   versions, P0-P3 priority, impact/confidence/effort, reason, expected effect,
   uncertainty, measurement and actual missing confirmations. Exact values and
   target placement must be established, not guessed from duplicate text. Public
   refreshes must use the reviewed bounded fetcher. Preserve site layout and static
   preview limits; allow measured text heights to reflow without proposing an
   unrequested production CSS edit. A rule-generated title is not clinical fact.

   Import through the strict seo-change-handoff/1 protected tracking interface.
   Validate all generated content as untrusted data before saving/import; reject
   cross-site references, executable content, oversized/malformed packets and
   unsupported targets. Output cannot grant approval, mark implementation or
   fabricate factual confirmations. Store immutable generated versions under
   protected ignored storage and include them through the existing credential-free
   backup/export validation. Never silently overwrite earlier reviewed documents.

6. An app review inbox/history with trigger reason, eligibility evidence, pending/
   running/completed/skipped/failed state, source limits, executor identity and
   current artifact version. Let the user open summary, recommendations, exact
   edits, previews and publication packet together, then reach existing tracking
   controls. Display outstanding clinician/owner questions and stale targets.
   Opening the app/rerunning widgets must not duplicate jobs, imports or approvals.
   Preserve explicit site/audit selection and existing reviewed artifacts. Add
   no external email/message notifications by default; an in-app new-packet badge
   is enough. Review generation never freezes/approves/publishes automatically.

7. Focused tests plus full regression suite, Streamlit AppTest and synthetic
   browser validation. Cover site/profile isolation, disabled defaults, threshold
   boundaries, missing/partial/empty sources, overlapping-window persistence,
   duplicate/retry/cooldown behavior, changed sources/targets/facts, interruption,
   timeout/cost bounds, workspace contention, strict output imports, prompt
   injection, credential isolation, failed executors, backup/restore and immutable
   prior approvals/history. Verify the app presents all packet versions correctly.
   Do not use real clinical/account evidence in tests or public PRs.

Update user documentation with the exact operational pipeline, executor/data/cost
requirements, settings, limitations and safe rollout/disable procedure. Report
checks actually run and distinguish implemented, synthetic-validated and live-
activated behavior. No website, CMS editor/autosave, security/hosting/DNS change,
Search Console write or broader OAuth access is authorized. Search Console stays
exactly https://www.googleapis.com/auth/webmasters.readonly. Live activation needs
a concrete reviewed setup packet and the user's authorization, independent of Git
merge permission. Private review artifacts never go into GitHub commits or PRs.
```
