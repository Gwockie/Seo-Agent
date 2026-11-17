# Disposable local WordPress title rehearsal

This bounded engineering route is separate from the production publishers and
the real site's proposals, approvals and receipts. It does not install a CMS
endpoint, modify publisher certificates or authorize production use.

## Observed result on November 17, 2026

**The end-to-end title rehearsal was not attempted.** Resource setup and baseline
capture worked, but credential preflight remained blocked after two focused
attempts. No forward save or restoration was performed; no successful save,
restoration, actual-stack certificate or complete title-effect coverage is claimed.

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
Consequently the requirement to exclude production credentials is unresolved, and
the title mutation remains blocked. The disposable services were stopped and their
volumes retained for review. There is no automatic retry or follow-on task.

Local evidence is under the ignored, access-restricted directory
`.tmp/title-rehearsal-20261117/` in the attached worktree. It includes clone and
isolation records, the raw stored baseline Title, raw HTTP captures and deterministic
sanitized captures, plus the final blocker/resource record. Copied source, secrets
and private captures are excluded from Git. The final evidence seal binds the
reviewed commit separately, avoiding a self-referential commit hash.

## Prepared scope, not applied

The sole intended test target is WordPress page `716`,
`/psychological-assessments-paoli/`. Its raw Title was
`Comprehensive Psychological Assessments`; the synthetic replacement would be
`Synthetic Local Title Rehearsal 20261117`. It makes no factual business claim.

The planned declarations cover the selected page's dynamic H1 in widget `022c973`,
breadcrumb label in widget `2be23dd`, document title and four navigation instances:
header menu item `771` and footer menu item `801`, each in main/dropdown menus.
The second declared page, `/contact-us/`, has those same four shared navigation
instances; its H1 and document title should remain unchanged. Canonical, robots
metadata and `X-Robots-Tag` should remain unchanged on both pages. An absent
Googlebot metadata field is unavailable rather than a confirmed unchanged value.
Other pages, save hooks, caches, scripts and browser behavior are outside this scope.

## Narrow implementation

`tools/local_title_rehearsal/runtime.py` is a fixed local resource-preparation tool,
not a general publisher. Its preparation is one-time; do not repeat partial setup.
It verifies the historical runtime review seal and private-folder protection and
uses only existing pinned images. It does not collect source or rebuild hosting.

`run.py` separates preflight, baseline capture, forward save, restoration and final
verification. The forward phase requires saved preflight and explicit scope files.
The blocked preflight is not present, so a forward invocation refuses to write.
Do not fabricate that prerequisite to bypass the unresolved environment condition.

`save-title.php` is mounted outside the web root and accepts only read/save for
the fixed page. It checks exact local instance, database, prefix, URL and isolation
settings. A local lock serializes this route's writers. A write checks the raw
current Title, then calls normal `wp_update_post(wp_slash(...), true)` and reads the
raw stored Title back. It does not substitute SQL or modify Elementor metadata.
It is not a multi-writer transaction certificate; the disposable runtime must have
no independent editors or writers.

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
Restoration would require exact raw Title equality, reverse declared checks and
exact sanitized baseline bytes; unrelated timestamps/revision rows need not revert.

## Focused validation

The tests cover exact raw-string restoration (including quotes/backslashes),
intervening-title refusal, lost replies before/after a possible write, unreadable
reconciliation, pending-attempt retry refusal, explicit API failure and invalid
attempt names. Existing title-effect and publication-verification tests run with
them. Their success validates the journal logic, not the unperformed WordPress save.

Current SiteGround compatibility, production caches and complete save-hook/effect
coverage remain explicitly unproven. Publication and production-impacting actions
retain the exact-action approval boundary in `website-change-policy.md`.
