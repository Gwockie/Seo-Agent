# From review to website implementation

Current workflow, October 10, 2026. Audit scheduling collects evidence; future
[scheduled review generation](review-generation-agent-prompt.md) prepares drafts.
Neither authorizes website writes. The app records exact proposals and human
approval, but has no CMS writer or deployment integration.

1. **Review the selected site and audit.** In **Recommendations & changes → Review
   together**, read Summary and Recommendations, then Proposed edits and the
   selected before/proposed capture. The written exact values govern scope;
   static copies are supplementary visual evidence, not a CMS layout certificate.
   Preserve the original public baseline and previous proposal versions.

2. **Revise and assess, then resolve facts and scope.** Use **Edit / Revise
   recommendation** or an exact action's **Edit / Revise proposal**, save a new
   revision and **Evaluate this saved revision**. Compare/restore proposals without
   changing observations, recommendation state or approval. See the
   [revision workflow](recommendation-revisions.md) for model-review availability
   and the private local handoff. The owner/clinician confirms actual services,
   location and clinical wording. In **Exact publication review**, open each
   action, enter its factual confirmation source, check the responsible-owner/
   clinician confirmation and **Save new proposal revision**. Never use a public
   claim or imported assertion as independent human confirmation. Confirm the CMS
   field and whether it affects only one page or a shared/global template. Expand
   the proposed action scope for review if a shared template affects more pages.

3. **Optionally validate isolated staging.** A verified staging editor, database,
   uploads, settings and deployment destination must be separate from production,
   with no live sync, customer messages or production jobs. Iterate there under
   the standing authorization and report each batch. A production draft/autosave
   is not isolated staging. If isolation is unknown, keep local copies. Creating
   staging on a production host needs approval for its concrete operational effects.

4. **Refresh and freeze.** Use **Refresh tracked pages**, then review/adopt the
   latest successful public capture in each relevant proposal revision. Current
   values must match the exact structural target, captures must be at most 24 hours
   old and assertions complete. Choose the exact latest actions and **Freeze
   selected publication batch**. Include affected URLs/settings, current/proposed
   values, intended edits, validation, factual confirmations and rollback. Unknown
   settings or unresolved targets need independent evidence before proceeding;
   do not alter the validator merely to make a batch pass.

5. **Human approval.** Review the frozen packet, check **I reviewed the exact
   actions, factual confirmations, validation and rollback**, supply who confirmed
   facts and when, type **I approve this exact publication batch**, then select
   **Record my exact human approval**. The agent must not click these controls on
   the user's behalf. Review state, proposed wording and available credentials do
   not authorize publication. Preserve approval's exact site/action/revision scope.

6. **Authorized implementation.** Give the implementing human/agent the frozen
   packet and approval reference through protected local access, plus a separately
   authorized WordPress access method. Preserve CMS revision/backup and rollback
   instructions. Recheck current values and approval validity immediately before
   writing. Record an attempt immediately before each action through the existing
   [receipt interface](automatic-change-tracking.md), apply only its approved
   values and record the actual result. Authorization covers the enumerated
   production editor/autosave/publish effects; additional pages/settings require
   their own exact approval. The app cannot perform this WordPress step today.

7. **Verify and record honestly.** Inspect the public rendered field and its exact
   location, relevant navigation/layout and canonical/index directives. Save a
   successful public snapshot and attach its reference to the receipt when
   applicable. Record failures and partial completion; public observation alone
   does not prove the author, approval or publication time. Changed wording/current
   targets, partial work, corrections or rollback require renewed affected-action
   review. Unaffected actions retain their exact authorization.

8. **Measure later.** In **Changes & results**, follow affected-page/query and
   whole-site trends with receipt/observation markers. Comparisons need compatible,
   equal complete finalized windows strictly before/after the actual reported
   implementation date. Missing rows remain unknown. Changes after an edit are
   observations, not proof of causality, qualified inquiries or Maps performance.

For an existing imported packet, do not create duplicate actions with **Track
these saved preview actions**. Revise its stable actions and confirm facts instead.
Refresh again if the public captures expire while reviewing. Approval of this
repository's code or documentation never grants website approval.

Search Console remains read-only. Indexing requests or sitemap/property writes
would need exact separate approval and separately authorized access, not expanded
scopes on the audit connection. No such write is part of this pipeline.

See [website-change policy](website-change-policy.md) and
[current tracking contracts](automatic-change-tracking.md) for the binding details.
