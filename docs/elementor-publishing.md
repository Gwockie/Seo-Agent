# Exact Elementor heading publication

The separate `elementor-heading/1` adapter connects the existing proposal/revision,
freeze, human approval, CMS review, Apply, verification and recovery workflow to
one page-local static heading, with exactly one action per review batch. Freeze and
review each page separately: a write changes the other pages' dependency tokens.
The core block adapter retains its restrictions.
Neither code approval nor a discovery import grants website publication authority.

## Certified scope

`wordpress/local-seo-publisher/elementor-contract.json` pins the exact synthetic
combination: Elementor 3.31.3, WordPress 7.1.3, PHP 8.3.35, MariaDB
11.4.13-MariaDB-ubu2404 and Twenty Twenty-Five 1.5. The manifest contains the official
Elementor archive hash and complete plugin/theme plus root/admin/includes PHP tree
hashes. The client also checks the exact companion PHP file hash and canonical
manifest hash. The server rejects different versions/files, MU plugins, drop-ins,
multisite, Elementor Pro, SEO plugins, persistent object/page/CDN caches and other
active plugins. Host deployment must be frozen during publication.

This deliberately narrow certificate covers published `elementor_canvas` pages
with an explicit excerpt, empty page settings, static heading widgets and default
container/section/column settings. Each widget has an explicit heading level;
shared/global/dynamic/template widgets, nested documents, linked/rich text and
unrecognized settings are rejected. Element caching must already be inactive.
Google-font fetching and telemetry must already be disabled and CSS uses internal
rendering, avoiding lazy remote-font downloads during verification. The existing
plain `post_content` mirror must consist of the corresponding
headings and whitespace. Existing generated CSS must be warmed and unchanged.

Elementor renders its title through `wp_kses_post`, so entity-like strings (including
semicolon-free forms), tags, control characters and shortcode brackets are rejected.
Ordinary Unicode and a literal spaced ampersand are supported. These restrictions
are stronger than offline mapping, which alone does not certify save/render effects.
Do not disable plugins, downgrade Elementor, change templates/excerpts or convert
the live site to make it fit this certificate. A broader installed stack needs its
own source review, effect contract and representative real integration tests.

## App workflow

1. Select the exact site/audit, revise existing tracked actions, and obtain the
   responsible human's factual confirmations. Refresh evidence, freeze the exact
   action revisions and record the existing human proposal approval.
2. In **Hosting & CMS**, save the actual provider and independent installation ID.
   Collect fresh public REST/rendered evidence and a protected administrator export
   containing exact page, metadata-row, template, mirror/excerpt and software
   inventory. Independently inspect the provider/CMS records and record the host
   effects review. For staging/local, also review every isolation condition against
   the connected production installation. A localhost address may be a tunnel and
   does not prove isolation. See [discovery](cms-discovery.md) for the full schema.
3. Configure a separate publication destination, choose **Elementor static heading**
   and select that exact discovery environment. Enter the dedicated application
   password only in the app password control. Discovery credentials are separate.
4. Map each frozen action to its explicit page ID, `_elementor_data` metadata row ID
   and widget ID. **Read CMS and prepare exact publication review** checks fresh
   independent endpoint state and public identity, creates the exact JSON/mirror
   candidate locally, and saves the row/path, old/new text, provenance, inventory,
   effects and inverse rollback. No generic content replacement is offered.
5. Review the exact one-action packet, record the separate CMS human authorization, and select
   **Apply these approved CMS actions**. Rollback needs its explicit authorization.
   The app repeats fresh raw/rendered checks before each request. Revisions, replaced
   evidence, disconnected environments, changed facts/configuration or stale captures
   block the affected actions.
6. Production preparation additionally requires a successful verified staging Apply
   of this exact action/revision, with matching source JSON/mirror/excerpt/template
   and certificate within 24 hours. The proof binds the exact attempt/request and
   still-current isolation evidence; another action in a partial batch cannot supply
   it. A staging receipt does not consume a separately approved production action.

Readiness distinguishes mapped, locally validated, staging validated and ready for
production review. It is never publication permission. Imported/restored history
is inert. The app reuses authoritative records, workspace locks, independent site
scope and the existing backup/migration protections; it does not create a second
chat-based approval system. Agents must not click human approval controls.

## Exact effect and recovery contract

The server locks posts/options/metadata inventory including insertion gaps in an
InnoDB transaction. It rechecks the full page, metadata, configuration, dependency,
file and generated-asset token. Filesystem deployments must be separately excluded
by the host. Conservative locks can delay other writes; use this contract only on
small independently validated installations.

It changes one JSON string token in the exact metadata row, its corresponding
heading text in the existing plain mirror, and the two page modification timestamps.
All other JSON bytes, layout, metadata, explicit excerpt and generated assets remain
unchanged. A before/after raw-data/mirror journal commits atomically. Only the page's
request-local `posts` and `post_meta` cache entries are evicted. There are no editor
sessions, save hooks, revisions, CSS regeneration, option writes or global cache
flushes in the publication transaction. Authentication can update application-password
last-used/IP bookkeeping and host access logs; those effects are disclosed.

The app records each attempt before HTTP, never automatically retries a CMS write,
and separates write success from verification success. Duplicate request IDs require
an identical body and return the committed receipt. A timeout requires read-only
reconciliation before an explicit resume with the same request. Known success stays
consumed after journal loss or a WordPress-only restore. Reconciliation retains the
frozen adapter route across credential rotation. Each batch page commits separately;
uncertainty or failed verification stops later actions.

Verification checks the exact raw candidate, mirror, row, token and surrounding
rendered content/directives. It is not visual/script execution certification. An
explicitly approved inverse restores the captured original JSON token, including
its original escape spelling, and original mirror bytes, only while the successful
write's whole-state token still matches. Concurrent edits prevent rollback. See
[publication recovery](wordpress-publishing.md) for the shared durable contracts.

## Separate installation approval

The app displays/downloads a deterministic companion ZIP with package and per-file
SHA-256 values. Its setup packet names the destination/provider/installation, three
files, journal-table/role activation, explicit instance/environment/user/page/contract
constants, minimal dedicated account, checks and recovery. Unknown provider or
installation facts remain blockers. There is no app installer.

An administrator must establish actual host compatibility and a protected baseline
first. Any production plugin install/activation, account/capability/configuration
change or staging creation on production infrastructure needs separate exact approval.
A content approval never permits deployment, DNS changes or a whole staging database
copy. On setup failure, deactivate/remove only newly installed files and restore the
prior constants/account state; retain journals for reconciliation. Do not request
passwords in chat. The Search Console scope stays `webmasters.readonly`.

## Reproduce synthetic validation

Use the repository virtual environment and `.tmp` for TEMP/TMP. Download the official
[Elementor 3.31.3 archive](https://downloads.wordpress.org/plugin/elementor.3.31.3.zip)
to `.tmp/elementor.3.31.3.zip`. The bootstrap requires SHA-256
`dfb51239e1ff09f1447f0d6ed42946367b7daefd78c5b4a072e352ebb7fe9e36`.
Only the disposable loopback Compose fixture is eligible; application passwords are
captured in process memory and never printed. Run core tests before Elementor setup:

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
docker compose -p lseo-publishing-test -f wordpress/compose.test.yml up -d
$env:LSEO_WORDPRESS_TEST = '1'
.venv-mvp/Scripts/python.exe -m unittest tests.test_wordpress_integration -v
$env:LSEO_WORDPRESS_TEST = '0'
$env:LSEO_ELEMENTOR_TEST = '1'
.venv-mvp/Scripts/python.exe -m unittest tests.test_elementor_integration -v
$env:LSEO_ELEMENTOR_TEST = '0'
.venv-mvp/Scripts/python.exe -m unittest discover -s tests -v
docker compose -p lseo-publishing-test -f wordpress/compose.test.yml down -v
```

Mocked app/UI tests validate authority, stale evidence, partial batches, uncertainty,
site switching and backup boundaries. Real Docker tests validate the pinned writer,
raw/mirror preservation, rendering, conflicts, duplicate requests, journal recovery,
permission restrictions and inverse rollback. Report which suites actually ran;
local success is not evidence that Meadow & Mind has passed verified staging.

Sources inspected: [Elementor data structure](https://developers.elementor.com/docs/data-structure/),
[CSS flush scope](https://developers.elementor.com/docs/cli/flush-css/),
[WordPress cache-hook effects](https://developer.wordpress.org/reference/functions/clean_post_cache/),
and the pinned archive's `includes/widgets/heading.php`, `includes/db.php`,
`modules/element-cache/module.php` and `core/files/css/post.php`.
