# Disposable local WordPress title rehearsal

This bounded engineering route is separate from the production publishers and
the real site's proposals, approvals and receipts. It does not install a CMS
endpoint, modify publisher certificates or authorize production use.

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

## Recover an interrupted attempt

Run from the attached rehearsal checkout with the repository's Python dependencies
available and the repository root on `PYTHONPATH`. Use the existing protected
rehearsal directory and retained disposable Docker containers.

1. Run `python tools/local_title_rehearsal/run.py recover forward` or
   `python tools/local_title_rehearsal/run.py recover restore` for the specific
   durable attempt. A live controller holds the local operation lock. If the
   recorded app generation is still running, the command journals unresolved
   state and exits unsuccessfully. Preserve the attempt and any result verbatim.
2. Confirm the exact retained disposable app identity and let any in-flight CLI
   writer finish. Stop and start only that app container to fence off the old
   writer generation. Keep the disposable database running and the historical
   baseline stopped. The guarded save rejects a delayed request from an old app
   generation before WordPress boots. Recovery validates the same app and database
   containers, isolation, mounts, mounted source and fixed page before accepting a
   read. The journal digest binds each observation to the original attempt.
3. Run the same recovery command from a fresh process. It appends a separate
   observation for the original, proposed, different or unavailable raw value.
   These values are relative to the attempt. For `restore`, the proposed value is
   the historical original Title. Observations describe current state. Keep all
   observations and inspect the named file if a record is incomplete or conflicts
   with the destination. Older journals without writer provenance cannot be
   upgraded by inference.
4. If forward recovery observes the synthetic Title, `run.py restore` is the
   separate guarded operation that can restore the exact original Title. An
   intervening Title or a conflicting settled observation blocks the save. If
   proposed-state capture was interrupted, restoration can capture it in a fresh
   directory while the synthetic Title is still present. If forward recovery
   observes the original Title, leave it in place and retain
   the attempted journal. A different or unavailable Title requires evidence
   review. Never retry by changing an attempt name or moving a journal.
5. Use `run.py verify` after restoration, including when `recover restore` observes
   the historical original Title. Verification captures fresh restored pages in a
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
