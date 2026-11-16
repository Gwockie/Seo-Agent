# Preparing an actual Elementor installation

In **Hosting & CMS → Prepare an exact saved Elementor action**, select an existing
audit action and its latest revision, then enter the independently observed page
and widget identities. Preparation uses current saved discovery evidence without
network or CMS writes. It works independently of publication configuration and
approvals, including when hosting access or an actual-stack certificate is missing.

The result preserves the audit/action/revision, profile and environment scope,
exact old/new wording, factual confirmation state and public/administrator evidence
IDs. It records specific preparation blockers or an offline JSON candidate.
Replacing either evidence source, changing the action or profile, disconnecting or
reconfiguring the environment, expiry or restoring a backup invalidates the result.
Referenced capture files, audit/rule context and the latest tracked source-page
observation are also bound, including for blocked reports. A conflicting newer
source observation blocks preparation until reconciled; a fresh local clone read
cannot supersede a conflicting production observation.
The captured structural action target must still identify the selected rendered
heading; equal text elsewhere is not a match.

An offline candidate changes exactly one JSON string and retains the original
string spelling, full source/candidate hashes, metadata-row assertion, widget path,
mirror/excerpt hashes and preserved sibling dependencies. Its local inverse refuses
any changed candidate and reconstructs the original bytes. This inverse does not
authorize CMS rollback. The existing strict mapper and synthetic writer remain
unchanged and reject a mixed dynamic/shared document.

The separate inspector preserves unrelated dynamic/shared sibling nodes, while
rejecting a selected dynamic/shared/global target or ancestor, linked/rich heading,
ambiguous identity, implicit heading level, multiline text or unsupported entity
spelling. Surrounding dependencies remain unresolved effects. An installed default
is not silently substituted for an explicit heading level. Do not convert a dynamic
title or choose a different heading to make a saved action pass. Revise the
authoritative proposal using fresh evidence when its current text/target differs.

Elementor describes [Post Title as the current post's title](https://elementor.com/help/dynamic-tags-pro-2/).
For an exact empty-settings dynamic `post-title` binding, a blocked result can
also explain the dependency. It first cross-checks the selected rendered heading
against the saved action's structural target. It retains the raw metadata and
binding hashes/path, asserted row ID and capture hash. The result
inherits the action, evidence, environment and freshness bindings above.

Discovery captures omit link labels and document titles. Their other title
references are explicitly unavailable, never counted as zero. This is a dependency
diagnosis, not a tested effect inventory.
Changing a source title can affect navigation, other widgets and document titles;
the full scope still needs independent evidence. The diagnostic does not assert
the stored post title, create replacement JSON, revise the action, validate staging
or enable publishing. Unknown/configurable tags and ambiguous rendered targets do
not receive this specific diagnosis. Static and dynamic publisher restrictions are
unchanged.

### Verifying title effects on isolated captures

`seo_agent.post_title_effects.verify_title_effects` compares two deterministic UTF-8
HTML captures of the same page. Give it the exact old and new literal titles and
an explicit list of `TitleEffect` rules for that page. Each rule specifies a CSS
selector, the expected number of matches and any fixed text before or after the
title. Use reviewed selectors that identify the actual widget or menu item and
link destination. Distinguish repeated navigation instances from distinct effects.

The comparison requires a whole text element at every declared location and
rejects an unlisted occurrence, an overlapping or ambiguous selector, changed
attributes or changes to any other captured bytes. It returns the input hashes
and substitution count. To verify restored captures, reverse the titles and
compare the resulting capture hash with the original baseline.

Use this narrow comparison on the preserved representative baseline where
sanitized captures are deterministic. Encoded or mixed-markup title text and
pages with unrelated byte changes are outside the supported comparison. Capture
collection, store state, effect scope beyond the supplied pages, browser behavior,
save hooks, caches, write attribution and authorization require their own evidence.

## What each result proves

| Result | Evidence | Remaining boundary |
| --- | --- | --- |
| Blocked preparation | Exact action and missing/unsupported inputs | Collect read-only evidence or revise the proposal |
| Offline candidate | Exact local JSON and rendered structural target | No mirror/save/cache/asset certificate, staging receipt or approval |
| Locally validated CMS review | Independent certified endpoint and current proposal | Separate human CMS authorization and explicit Apply |
| Staging validated | Successful exact request and verification on independently reviewed local or hosted staging | Matching production contract/source and fresh host evidence |
| Production review ready | Matching endpoint, source, widget/path and staging proof | Exact production approval and Apply |

Verified **local** staging can supply the same prerequisite as hosted staging.
A localhost URL alone is insufficient. The app rechecks dated isolation evidence,
the original review fingerprint and destination, exact action revision and CMS
authorization, request, source, widget/path and server receipt. Credential rotation
does not change installation identity. Partial batches, altered/lost receipts,
stale isolation and restored history cannot certify production. A separately
authorized inverse retains historical successful validation; failed reconciliation
invalidates it.

## Completing an actual-stack certificate

The offline result is not an extension of `elementor-heading/1`. Before offering
setup/publication for a different installation, independently establish:

- Fresh installation/access identity, DB vendor/engines, raw metadata row IDs,
  mirror/excerpt/template and generated assets.
- Active plugin/theme/core/drop-in source hashes, shared documents, active kit,
  settings/experiments and deployment exclusion.
- Save/render hooks, mail/jobs/webhooks and each host/plugin/CDN cache layer,
  with precisely scoped invalidation and recovery effects.
- A representative isolated copy with production services disconnected, separate
  baseline/test resources and faithful rendering where validation requires it.
- A separate pinned server/client contract with real apply, conflict, uncertainty,
  reconciliation, journal-loss, credential-rotation, verification and inverse tests.

Elementor stores layout in post metadata; inspect normal save/cache behavior
independently. [Elementor data structure](https://developers.elementor.com/docs/data-structure/).
WordPress `clean_post_cache` invokes hooks and invalidates entries beyond the
selected post. [WordPress reference](https://developer.wordpress.org/reference/functions/clean_post_cache/).
SiteGround documents several server cache layers and dynamic caching that can
operate without its WordPress plugin. A missing plugin or one public response
therefore does not establish absent host caches.
[SiteGround caching](https://www.siteground.com/tutorials/wordpress/speed-optimizer/supercacher).

Keep actual production setup blocked until those effects and local validation are
known. Installation/activation, accounts/capabilities, deployment, publication and
temporary host cleanup retain their separate exact-action approvals. See
[website change policy](website-change-policy.md) and
[Elementor publishing](elementor-publishing.md).

For an already downloaded, separately approved source collection,
`seo_agent.source_manifest.manifest_archive` creates an inert file manifest from
an exact retained archive SHA256, one wrapper directory, and explicit relative
directory/file allowlists. It checks the ZIP directory bounds before loading the
entry list, checks the complete indexed local-record layout, rejects path aliases,
unexpected files, links, special files, encryption, unsupported layouts and
expansion limits, and verifies each file's length/CRC/SHA256 and complete compressed
payload. Path depth and derived tree size have separate limits. It rereads the
archive hash before returning. No files are
extracted or executed, and the function makes no network or app-record writes.

Every approved source item must be present. Recursive code roots include packaged
descendants such as vendor test files and packaged `.htaccess`; a collector must
not promise descendant exclusions that a whole-folder copy cannot enforce.
Callers must keep archives/manifests protected, screen source for sensitive data,
retain collection provenance and approvals, and independently verify live identity,
freshness and isolation before any execution. A manifest's canonical tree digest
supports byte comparison; it is not a publisher source certificate, complete
activation inventory or proof that the source contains no credentials. ZIP64 and
multipart archives are unsupported; do not silently loosen bounds to accept them.
The default path policy rejects case/Unicode aliases for portable storage. An
explicit `path_semantics="posix"` preserves case-distinct Linux source paths in
the inert manifest, with that policy bound into its tree digest. Such a manifest
does not establish that extraction onto Windows would preserve those files.

The setup packet and readiness report retain known inventory conflicts as well as
missing evidence. The pinned Elementor preflight compares explicit live table
roles, engines, versions, hashes and active software. It distinguishes preparation
before installation (the companion and journal may be absent) from host review
after installation (both must be present). Complete category labels or a human
checkbox cannot override incompatible or missing inventory rows.

MyISAM cannot supply the existing contract's atomic content/mirror/journal
transaction: [MySQL documents that nontransactional changes cannot be rolled back](https://dev.mysql.com/doc/refman/8.4/en/nontransactional-tables.html).
The disposable Docker tests replace each required synthetic table's
engine in turn and verify that both publishers reject state reads and fresh writes,
preserve exact rows and timestamps, and retain read-only reconciliation of earlier
success. This is rejection coverage, not a MyISAM publishing certificate. Keep the
preserved site baseline separate and do not convert live tables to fit the tests.
