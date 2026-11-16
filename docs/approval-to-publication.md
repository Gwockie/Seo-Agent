# From review to website implementation

Current workflow, October 10, 2026. Audit scheduling collects evidence; future
[scheduled review generation](review-generation-agent-prompt.md) prepares drafts.
Neither authorizes website writes. The app records exact proposals and human
approval. An opt-in [WordPress heading publisher](wordpress-publishing.md) now adds
CMS mapping review, separate exact CMS human authorization, explicit Apply,
per-action receipts, reconciliation and authorized rollback. It remains disabled
until a human configures the destination and separate protected CMS credentials.
The separate [Elementor heading adapter](elementor-publishing.md) uses these same
authoritative proposals, frozen revisions, approvals and receipts. It requires
current hosting evidence and a successful isolated staging Apply of the exact
action revision before preparing its production CMS review. This is separate from
the core adapter; public widget mapping does not establish compatibility.

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
   their own exact approval. For the narrow supported WordPress combination, use
   the app's CMS review and Apply controls described in the publishing guide.
   For a dynamic Elementor Post Title heading, use the manual procedure below.

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

## Manual WordPress page title update

Use this option for a saved whole-heading proposal whose Elementor widget takes
its text directly from the WordPress page Title. In **Edit / Revise proposal**,
select **Manual WordPress page title update**, enter the page and widget IDs, and
reference current read-only CMS evidence for the raw Title and dynamic binding.
Describe each known title-dependent surface, its affected URL and expected change,
including navigation, other widgets and the document title. Resolve unknown
effects before approval. Public HTML can tie the saved heading to the widget but
cannot establish the raw Title, the binding or the complete effect scope.

Save and review the revision, resolve its factual confirmations, and refresh the
public baseline. Freeze this action by itself. The frozen review shows the exact
production Title change, the widget, the mapping evidence, the shared effects,
and the inverse candidate. Human approval explicitly covers opening the specified
production editor, its autosaves and updating the single Title field. Obtain
separate authorization for CMS access.

Before opening the editor, recheck the live CMS baseline and effect scope using
authorized read-only evidence, preserve the existing revision reference, and
select **Record start of manual attempt** in the app. Follow the steps for that page,
enter the actual outcome time in UTC and save the operator report. Record partial
or uncertain outcomes as such. The app blocks another manual attempt for the
same page across action IDs and revisions until the earlier attempt has public
heading verification or a recorded operator reconciliation. Use **Record
operator reconciliation** after checking the raw CMS Title and shared effects
with read-only access. Imported receipts cannot start a manual title attempt
or substitute for the app's reconciliation controls. An unresolved automated
production attempt blocks a manual start on the same page, and an unresolved
manual attempt blocks an automated write there.
An automated attempt with an uncertain write outcome in restored history
requires separate recovery against the matching installation. Restoring the
workspace does not clear uncertainty or renew write authorization.

Use **Refresh tracked pages** after publication. If needed, add the exact URL in
**Tracked pages and check settings**. A successful later capture showing the
exact proposed heading at the frozen structural target and widget can be recorded
with **Record independent public heading verification**. Compare the document
title, links to this URL and index directives with the frozen baseline. The
verification covers the observed public heading. Check the remaining shared
surfaces, raw CMS state and cache behavior using separately authorized access.
The journal stores the operator report and observation separately.
Record an operator reconciliation if the raw Title or other observed effects
conflict with a matching public heading. Both observations remain in the journal.

For rollback, confirm the current raw Title, revision and affected surfaces,
prepare an exact inverse review with the current Title and original Title, and
obtain new human approval before opening the editor. To track the inverse in the
app, save it as a new proposal grounded in a fresh heading preview that shows the
current Title. Recheck the same public surfaces afterward. Partial or uncertain
results require their actual state before the inverse can be specified.
