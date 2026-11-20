# Disposable local WordPress title rehearsal

This bounded engineering route reads a saved proposal and records isolated
staging evidence. Production publishers, approvals and implementation receipts
are outside this route.

## Initial preflight block on November 17, 2026

Resource setup and baseline capture worked. Credential preflight remained blocked
after two focused attempts, so the initial run ended before any Title save. The
follow-up below records the later successful rehearsal.

The preserved historical project `lseo-meadow-representative-20261021` remained
stopped. Its site and database volumes were mounted read-only, hashed, copied to
new volumes and compared byte-for-byte (including file modes and ownership). The
new project is `lseo-title-rehearsal-20261117`, with `-app` and `-db` containers and
`_site`, `_database`, `_dbsocket` and `_httpsocket` volumes. Both runtime containers
used `network:none`, read-only root filesystems, dropped capabilities and no
published ports. The editor path is Docker-local CLI only; the renderer and database
communicate over separate disposable Unix socket volumes. Local config and service
guards were mounted read-only. The historical checkout and baseline were preserved.

The copied runtime successfully intercepted synthetic mail, external HTTP and a
scheduled event; public indexing was disabled. Screening the copied options first
rejected serialized plugin objects and core formats/routes. The second focused
attempt decoded serialized values without instantiating classes, checked core
format/route grammar separately, and still rejected a nonempty sensitive key.
Screening was stopped without weakening the check or displaying credential values.
The initial run stopped the disposable services and retained their volumes. Its
credential rejection and blocker records remain historical evidence.

Local evidence is under the ignored, access-restricted directory
`.tmp/title-rehearsal-20261117/` in the attached worktree. It includes clone and
isolation records, the raw stored baseline Title, raw HTTP captures and deterministic
sanitized captures, plus the final blocker/resource record. Copied source, secrets
and private captures are excluded from Git. The final evidence seal binds the
reviewed commit separately, avoiding a self-referential commit hash.

## Successful credential-screening follow-up in PR #28

The installed Rank Math vendor source, `wp-content/plugins/seo-by-rank-math/vendor/wp-media/mcp-oauth/inc/Auth/SecretManager.php`, declares the exact top-level `mcp_jwt_secret` option as its 256-bit OAuth JWT signing key. Its generator stores lowercase hex. `inc/Bootstrap.php` runs its initializer on WordPress init. The follow-up therefore clears the verified scalar in the disposable copy via `update_option` and retains the empty row. The installed initializer's `add_option` cannot replace an existing empty row. The next preflight boots WordPress independently and verifies the empty option.

The follow-up retained the exact signing-option rejection, journaled the one-time
sanitization and verified the existing empty row. An independent WordPress boot
passed the credential screen and isolation probes. The rehearsal saved the
synthetic Title, verified the two declared renders, restored the original raw
Title and verified both restored renders. The historical baseline remained stopped
with unchanged volume manifests. The disposable containers were stopped and their
volumes retained. Keep the original preparation and the protected
`credential-screening-resume/` evidence. Recovery reuses this evidence without
repeating preparation or credential sanitization.

The historical option screen still decides pass or fail over the same option input. Failure diagnostics use an allowlisted name for the verified static option and positional paths for dynamic keys. The screen covers the documented keys and credential shapes within options, along with the separately checked core format and rewrite grammar. It cannot establish that every field or storage location is free of credentials.


## Rehearsed scope

The sole test target is WordPress page `716`,
`/psychological-assessments-paoli/`. Its raw Title was
`Comprehensive Psychological Assessments`; the synthetic replacement was
`Synthetic Local Title Rehearsal 20261117`. It makes no factual business claim.

The declarations cover the selected page's dynamic H1 in widget `022c973`,
breadcrumb label in widget `2be23dd`, document title and four navigation instances:
header menu item `771` and footer menu item `801`, each in main/dropdown menus.
The second declared page, `/contact-us/`, has those same four shared navigation
instances; its H1 and document title should remain unchanged. Canonical, robots
metadata and `X-Robots-Tag` should remain unchanged on both pages. An absent
Googlebot metadata field is unavailable rather than a confirmed unchanged value.
Other pages, save hooks, caches, scripts and browser behavior are outside this scope.
All four navigation instances belong to the literal capture comparison. The raw
publication verifier checks the two visible main-menu instances; it treats hidden
dropdown ancestors as unavailable. Dropdown text remains explicitly checked by the
literal verifier, without changing the publication verifier's static-body semantics.
The historical sanitizer's URL allowlist also omits port `18718`, so these retained
sanitized captures have no local link destinations. Literal rules bind exact menu
and item identities; visible raw rules additionally bind the full destinations.
Hidden dropdown destination attributes are outside the supported raw checks.

## Narrow implementation

`tools/local_title_rehearsal/runtime.py` is a fixed local resource-preparation tool,
not a general publisher. Its preparation is one-time; do not repeat partial setup.
It verifies the historical runtime review seal and private-folder protection and
uses only existing pinned images. It does not collect source or rebuild hosting.

`run.py` separates preflight, baseline capture, forward save, restoration and final
verification. The forward phase requires the retained passing preflight, original raw Title,
historical baseline and complete fixed scope. The recovery journal lives in the
protected `interruption-recovery/` directory beside the prior successful evidence.

The scope validator requires exactly the two fixed URLs in capture order and the
complete fixed selectors, values and effect kinds above. Both effect lists must
be nonempty. It rejects omitted, duplicated, additional or altered checks before
calling the save backend; comparison revalidates scope and capture URLs. Empty
declarations cannot produce a successful report. `expected_scope` documents the
exact JSON contract using the two original captured document titles. This is a
bounded declaration for these two pages, not a claim of complete site coverage.

`save-title.php` is mounted outside the web root and accepts only read/save for
the fixed page. It checks exact local instance, database, prefix, URL and isolation
settings. A local lock serializes this route's writers. A write checks the raw
current Title, then calls normal `wp_update_post(wp_slash(...), true)` and reads the
raw stored Title back. It does not substitute SQL or modify Elementor metadata.
The disposable runtime must have no independent editors or writers. The write
requires the app generation recorded by the controller.

`seo_agent.local_title_rehearsal.transition` durably records an exclusive attempt
before calling the backend. It reads actual state even after a lost response and
distinguishes applied, failed, conflict and uncertain results. A pending/completed
attempt name cannot be retried. Restoration is a separate guarded transition which
refuses an intervening raw Title. `applied` describes the read-back title state,
not independent proof of authorship or all save-hook effects.

Actual HTTP response bytes are retained. The existing reviewed preview sanitizer
is used only to create an additional deterministic capture; it is not the evidence
of the save. Its removal of active markup and metadata limits its scope. The
unchanged `post_title_effects.verify_title_effects` compares those sanitized captures
with explicit literal locations. The existing publication verifier's capture,
observation and comparison functions check the raw captures independently,
including metadata. The regular report intentionally rejects private URLs; this
local tool uses its same lower-level comparison semantics without creating app
snapshot, approval or receipt records or changing that public-URL restriction.
Restoration verification requires exact raw Title equality, reverse declared checks and
exact sanitized baseline bytes; unrelated timestamps/revision rows need not revert.

## Rehearse a saved proposal

Launch the normal loopback app with `python -m seo_agent app --local-title-rehearsal`
from the main checkout, or select the registered `workspace/private` explicitly
with the global `--workspace` option. Select **Meadow & Mind** and its original
audit in **Recommendations & changes**. The private route requires the protected
workspace, the exact registered site identity and psychology profile, and the
current revision of the bound saved action. The saved action must target
`https://meadowandmindpsychology.com/psychological-assessments-paoli/` as a
reviewed Post Title text change on page `716` and widget `022c973`. The app
verifies those details and shows the proposal and isolated destination separately.

For synthetic use, launch `python -m seo_agent app --demo --local-title-rehearsal`
and select **Demo psychology A**,
then open the selected audit in **Recommendations & changes**. Use a saved `text`
proposal on `https://psychology-a.example/psychological-assessments-paoli/` with a
reviewed Post Title mapping to page `716` and widget `022c973`. The proposal must
use the fixed original raw Title as its baseline. The app explicitly maps that
synthetic source to the fixed Docker page and validates the Post Title widget in
the local runtime. Plain text must also meet the writer byte bound and the
unchanged raw and literal verification rules.

Open **Rehearse this proposal on local staging** to review the saved revision,
observed local baseline, replacement, destination and declared effects. Pending
owner or clinician questions remain pending and are displayed with the staging
draft. **Apply saved Title** rechecks the stored revision, mapping, writer
generation, scope and raw Title. Form edits enter this flow after saving a new
revision. Rehearsal status grants no production approval or SiteGround assurance.

The forward journal freezes the source workspace, mode, site profile, audit,
action ID, revision, proposal digest, destination, raw Title pair and digests
for the two-page scope and baseline captures. The private and demo views expose
their own runs. Existing demo journals retain their original mapping and identity.
An unresolved run holds the shared Docker target for both modes. Raw readback
and reconciliation observations, rendered checks and
restoration verification have separate displays. A subsequent edit makes earlier
results historical in the proposal panel. Recovery and restoration still use the
original journal. **Hosting & CMS** also provides those controls for the active
run on the source site, including retained runs from before proposal binding.

Both views use the registered runtime at
`C:/Personal Projects/seo-agent/local-seo-agent/workspace/private/local-staging/title-rehearsal`.
This path is independent of the checkout and of the app's proposal workspace.
The registration binds the replacement app and database IDs, exact read-only
mounts, pinned writer and support files, and fresh two-page baseline. Missing
registration or journal directory, changed files, incompatible code and
mismatched containers block execution. The app reads the registration and uses a read-only database
transaction to observe the Title, heading binding and isolated database
settings without loading WordPress. Apply and Restore repeat the live WordPress
preflight as part of the explicit operation.
In **Hosting & CMS**, select **Start local staging** to start the registered
database and wait for its socket before starting the registered app. The
controls check the registered identities, isolation, mounts and volume use
and share the Title operation lock. A failed start displays the observed
container states so you can retry from a running database or explicitly stop
the pair. If the app is running while the database is stopped, stop the app
before starting the pair.

Select **Stop local staging** to stop the app before the database. Stop
refuses a live Title writer and holds the writer lock until that app
generation exits. If Docker cannot confirm the app stopped, the database
keeps running. A subsequent Stop can finish the fenced shutdown. Opening,
refreshing or restarting the SEO app only inspects state.
Both controls preserve the registered containers, volumes and all Title
journals, including pending outcomes. Keep both retired disposable containers
stopped because the registered pair uses the same four volumes.

App runs are stored in `app-rehearsals/run-000001` and subsequent numbered directories
inside the stable protected directory. A subsequent run requires an observed
restoration and passing explicit verification of the previous run. An interruption
that leaves only evidence of the original value, or leaves incomplete rendered
evidence, requires journal review before another run. Keep all records in place.

## Compare saved WordPress captures

In the saved proposal's rehearsal panel, open **Compare saved WordPress captures**.
Select a run and either of its two local pages. Historical runs retain their saved
revision number. **Compare all** shows the registered baseline, the completed staged
capture and the capture taken during Restore side by side when space allows.
In a narrow window the recorded values stack. Select **Before**, **Staged** or
**Restored** to read the full capture at either width.
The comparison matches the displayed sanitized HTML to the recorded digests and
checks the retained raw HTML against its capture manifest and recorded observations
for the declared locations. The later-phase reports independently record the
sanitized digests. A missing or unbound phase is unavailable. The legacy demo
journal predates workspace binding and is excluded from the comparison.

The controls work while the staging pair is stopped. The page view shows captured
text and basic document structure with site styles, images and links removed.
Page headings, breadcrumb text and navigation labels are visible where captured.
The separate document title comes from the capture. Mobile layout, live appearance
and production compatibility remain outside these checks.

## One-time migration of the recovered rehearsal

The explicit operator command
`python -m tools.local_title_rehearsal.migrate check` checks the known recovered
inputs, retained journals, independently reviewed sources and stopped Docker
resources. Run `python -m tools.local_title_rehearsal.migrate migrate` only for
this recovered installation. It takes the old controller lock, checks all
canonical prior attempts, and briefly starts the old isolated pair to read the
original raw Title. It stops that pair before creating or starting the
replacement. The historical representative project stays stopped throughout.

The command copies private inputs exclusively into the protected stable
directory, checks byte equality and Windows access, and captures fresh local
preflight and rendered baseline evidence with the replacement pair. It stops
the replacement pair and checks the historical baseline's volume manifests
before activating the runtime. The private `migration-manifest.json` records
source paths, SHA-256 digests, old and replacement identities and validation
results. Historical bytes are in `history/old` and
`history/saved-proposal`. Historical journals retain their original identities
and cannot become active attempts. The replacement's first new app run starts
at `app-rehearsals/run-000001` and uses a new operation lock. The old lock stays
in the recovered source.

An existing destination or a conflicting resource blocks migration. A
directory without a complete registration stays inactive. Preserve any partial
copies and replacement resources for inspection. App launch leaves provisioning
and migration to the explicit operator command.

## Recover an interrupted attempt

Open the active saved proposal or the source site's **Hosting & CMS** panel in
the opted-in loopback app. The controls use the originating workspace and the
frozen binding in the registered runtime's journal.

1. Use **Recover interrupted attempt** for the durable attempt. A live
   controller holds the local operation lock. If the recorded app generation
   is still running, recovery records unresolved state. Preserve all records.
2. Confirm the exact registered disposable app identity and let any in-flight CLI
   writer finish. Use **Stop local staging**, then **Start local staging** to
   fence off the old writer generation. Keep the historical baseline stopped.
   The guarded save rejects a delayed request from an old app
   generation before WordPress boots. Recovery validates the same app and database
   containers, isolation, mounts, mounted source and fixed page before accepting a
   read. The journal digest binds each observation to the original attempt.
3. Reopen the app and use **Recover interrupted attempt** again. It appends a separate
   observation for the original, proposed, different or unavailable raw value.
   These values are relative to the attempt. For `restore`, the proposed value is
   the historical original Title. Observations describe current state. Keep all
   observations and inspect the named file if a record is incomplete or conflicts
   with the destination. Older journals without writer provenance cannot be
   upgraded by inference.
4. If forward recovery observes the saved Title, **Restore original Title** is
   the separate guarded operation. An
   intervening Title or a conflicting settled observation blocks the save. If
   proposed-state capture was interrupted, restoration can capture it in a fresh
   directory while the synthetic Title is still present. If forward recovery
   observes the original Title, leave it in place and retain
   the attempted journal. A different or unavailable Title requires evidence
   review. Never retry by changing an attempt name or moving a journal.
5. Use **Verify restoration** after restoration, including when recovery observes
   the original Title. Verification captures fresh restored pages in a
   separate directory, checks the retained proposed-state captures against the
   declared forward and reverse changes, and checks the raw Title and original
   volume manifests. Missing or failed rendered checks leave verification
   incomplete. Partial capture files from an earlier process are preserved.

## Interruption exercises on November 17, 2026

The disposable WordPress save returned the synthetic Title before the first
controller exited without a result record. Recovery on the original app generation
recorded unresolved state. After restarting only the disposable app, fresh recovery
observed the synthetic Title. A separate guarded restoration returned the original
Title and passed the declared rendered checks.

After verified restoration, a second fault controller exited after journaling its
attempt and before dispatching the save. Two fresh recovery processes observed the
original Title. Across both exercises, the private transport traces recorded zero
recovery save dispatches. Final verification matched the original raw Title,
both rendered page declarations and both sanitized baseline captures. The
historical baseline and PR #28 evidence remained unchanged. Private recovery
journals and transport traces are retained under the ignored rehearsal directory.

## Focused validation

The tests cover exact raw-string restoration (including quotes/backslashes),
intervening-title refusal, lost replies before/after a possible write, unreadable
reconciliation, pending-attempt retry refusal, explicit API failure and invalid
attempt names. Synthetic interruption tests cover both interruption points,
unchanged and changed values, unreadable state, repetition, malformed evidence and a destination mismatch.
They assert that recovery makes zero save calls. Existing title-effect and
publication verification retain their declared checks.
Scope tests additionally confirm empty, missing, extra and reordered pages, empty
effect lists, omitted or duplicate checks, changed selectors/values and unsupported
rule types are rejected before any backend read or write.

Current SiteGround compatibility, production caches and complete save-hook/effect
coverage remain explicitly unproven. Publication and production-impacting actions
retain the exact-action approval boundary in `website-change-policy.md`.
