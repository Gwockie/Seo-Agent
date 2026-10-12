# Exact WordPress publication, version 1

Publishing is off until a human configures the selected destination and a separate
CMS credential. This implementation does not configure or write any real site.
Audits, scheduled reviews, imports, model output and historical receipts cannot
grant publication authority. Search Console remains `webmasters.readonly`.

## Supported scope

The first adapter supports **one plain-text `core/heading` block per published
WordPress page**, with a unique explicit HTML anchor and top-level block index.
Each action maps the app site, source URL, destination URL, installation ID, numeric
WordPress page ID, `post_content:core/heading`, anchor and block index. It consumes
an existing frozen exact `text` action; a selector alone is never a CMS mapping.
The captured public target must resolve to that same anchored heading.

Validated locally with WordPress **7.1.3**, PHP **8.3** and MariaDB **11.4** using
the image digests pinned in `wordpress/compose.test.yml`. Other versions have not
been certified; repeat the local/staging contract suite before enabling them.

The companion currently accepts WordPress core blocks with Twenty Twenty-Five,
only flat core paragraphs/headings, a fixed explicit page excerpt, the companion
as the sole active plugin, no must-use plugins/drop-ins/multisite, and no custom
page template or saved shared template overrides. Ordinary link-only navigation
is inspected and allowed. Query loops, reusable blocks, shortcodes, block bindings
and other shared content rendering cause rejection. Inventory, theme file hashes,
template/global style hashes, full page row and metadata participate in conflict
detection. Explicit excerpts prevent heading edits from changing generated search
excerpts. Host-level rendering/cache customizations need separate validation.

Unsupported: post/page **titles** (`post_title`), visible theme-generated titles,
SEO titles/descriptions, Yoast/Rank Math/AIOSEO metadata, Elementor/Divi/Bricks
widgets, classic-editor HTML, rich/linked heading text, nested headings, shared
patterns/templates, posts/custom post types, new pages, status changes, redirects,
canonical/robots/settings writes, plugin installs, DNS, deployment, and more than
one action per page in a batch. Rejecting unsupported structures is intentional;
do not convert them into whole-content replacement or generic REST writes.

Public HTML and the actual local WordPress database/REST responses were inspected
read-only before write tests. The local fixture verifies block attributes, raw
content, metadata preservation, page identity and editor/plugin inventory. No
production CMS compatibility is claimed without separate discovery.

## Review and apply

1. Review/revise the proposal, confirm facts, refresh public evidence, freeze the
   exact batch and record the existing human proposal approval.
2. Under **Exact publication review → WordPress publication destination**, the
   human configures the independent instance ID, canonical home URL, environment,
   dedicated username and application password. Production must exactly match the
   selected profile's canonical site URL. Staging/local destinations must be
   separate; record host evidence for independent editor, database, uploads,
   deployment destination, no production sync/jobs/customer messages, restricted
   access and noindex. A staging-looking URL is not evidence. If these facts cannot
   be established, use the local fixture. Path translation preserves the source
   URL's suffix under the selected staging home.
3. Enumerate each page ID and core heading anchor. **Read CMS and prepare exact
   publication review** only reads the CMS/public site and stores a local packet.
   It includes current/proposed values, owner confirmations, CMS inventory and
   tokens, public baseline, validation, exact write scope and inverse rollback.
4. The human reviews the packet, supplies the confirmation source, types
   **I approve these exact CMS writes**, and explicitly approves this review.
   Optionally include the enumerated rollback. The prior proposal approval alone
   cannot authorize CMS effects that were not yet mapped and reviewed.
5. The human selects **Apply these approved CMS actions**. Public validation must
   be current under the existing 24-hour capture rule; every CMS/public preflight
   is fetched anew. Exact authorization persists while that scope remains valid.
   Destination changes, proposal revisions, changed facts/configuration,
   validation failures and CMS/public changes block the affected writes.

The human UI submit handlers are the authority boundary for this trusted,
single-user desktop app, as in the existing approval workflow. A boolean is not
remote authentication: a malicious process running as the same Windows user can
modify Python/SQLite or use that user's vault. Run Streamlit on loopback only,
retain its CSRF/XSRF protection, restrict the workspace to the owner, and never
expose these controls as an unauthenticated network service. Agents must never
click the human configuration/approval/apply controls on someone's behalf.

## Exact server effects and preservation

Each request first locks the options and posts inventory (including insertion gaps)
in a short InnoDB repeatable-read transaction, then locks the page metadata and compares
the fresh installation/URL/content/metadata/configuration token. Cached option
values must agree with fresh database values. This prevents navigation, global
style, plugin-option or shared-content changes from racing the decision. These
conservative locks can briefly delay other CMS writes; use this narrow adapter
only on small supported sites and validate contention on isolated staging. Theme
or core file deployments must be excluded during publication by host coordination;
database locks cannot serialize filesystem deployment. The adapter changes only
the approved heading's text bytes in `post_content` plus `post_modified` and
`post_modified_gmt`. All other page bytes and metadata are preserved. It commits
a unique request journal containing before/after content in the same transaction,
then invalidates the page's WordPress object cache. There are **no editor sessions,
drafts, autosaves, generic `wp_update_post` hooks or WordPress revision writes**.
The companion journal and app packet are the captured rollback baseline. Bypassing
save hooks is deliberate and is why other plugins/builders/cache integrations are
unsupported. Do not extend this adapter to them without designing their effects.

The server's independent page-ID/user allowlists and unique installation constant
are mandatory. A request ID cannot be reused with different values. Ordinary
WordPress row updates serialize with the transaction. Changes between app preflight
and the write are detected again by the server. A multi-page batch is not atomic:
preflight checks all remaining actions, then applies and verifies them one by one.
The first uncertainty/verification failure stops later actions. Earlier successes
remain recorded and require explicit rollback if desired.

## Attempts, receipts and recovery

The app commits a unique attempt before sending a request. A workspace operation
lock coordinates publishing with audit/backup/restore/review work. Final local
approval checks and the HTTP write hold the SQLite write lock so a concurrent
proposal save cannot slip between them. Attempts/events survive interruption;
ordinary duplicate Apply clicks never resend an existing attempt. Attempt identity
includes the stable home URL, installation ID and environment; credential rotation
cannot reset it. A staging receipt does not consume a separately reviewed production
action. Schema migration preserves old attempt IDs, destinations and events.
Reconnecting to the same stable installation allows read-only reconciliation with
the current credentials. It does not revive the old authorization to write.

**Reconcile destination (read only)** reads the server request journal and current
page. A matching field alone does not prove this app wrote it. A missing server
journal entry is **uncertain**, not proof of failure. **Reconcile then resume the
same approved request** first reads the journal, rechecks still-current approval,
CMS values and public baseline, and reuses the same request ID/body. A delayed
original request and the retry cannot both commit. No automatic retries or
publication scheduling exist. If public evidence is stale, refresh it; unchanged
exact values/targets preserve their authorization. Changed wording, destination or
CMS state blocks resume. Preserve the attempt and obtain operator evidence resolving
any in-flight request before preparing another revision; never delete journal rows
to unblock a page. A new revision cannot bypass an unresolved page request.

Once the app has proof that a request succeeded, that authorization stays consumed.
A WordPress-only restore or lost server journal cannot turn that request into a
retryable failure. Reconciliation reports the missing journal while preserving the
known write result. Plain heading values are treated literally, including text
that resembles HTML entities; unsupported shortcode brackets and values that
cannot be rolled back by this adapter are rejected during preparation.

Receipts distinguish **write succeeded** from **verification passed/failed**.
Verification checks the server request identity, fresh CMS token, exact heading,
all remaining raw page bytes, metadata hash, rendered heading, adjacent HTML,
links, canonical/robots/meta/JSON-LD and X-Robots-Tag. Render comparisons ignore
executable script/style bodies and comments. These are static-content checks,
not a visual layout/accessibility or script execution certificate. Dynamic markup
can fail conservatively; no automatic overwrite or rollback follows a failure.
Application receipts also feed existing implementation history/trend markers;
CMS events retain exact per-action verification evidence.

Rollback writes the captured old heading using the original successful write's
whole-page token. It stops after **any** subsequent page/metadata/configuration
change, including a human edit, even if the heading itself still matches. Human
rollback authorization must have been explicitly included in this exact packet;
otherwise prepare a new inverse proposal with fresh evidence and exact human
approval. Rollback is not automatic and does not make the old Apply reusable.

Backups contain no passwords. The backup database itself is sanitized before
archiving: CMS destinations disabled, credential references detached, approvals,
reviews and attempts marked history-only. Restore repeats those protections,
generates a new destination generation, and requires human reconfiguration with
new vault references and fresh approvals. This also protects interrupted restore
extraction. Raw filesystem cloning is not the supported backup/restore workflow.

## Separately approved host setup

Installing the companion on a production host is a production plugin change and
requires its own exact approval. This repository does not install it there.
After separate approval, an administrator would:

1. Verify a stock supported core/theme installation, full backup, TLS and host
   isolation/cache behavior. Verify theme/core checksums against official releases.
2. Install `wordpress/local-seo-publisher/` as the only active plugin for a supported
   environment. Activation creates an InnoDB `*_lseo_operations` table and the
   `lseo_publisher` role. Its capabilities are only `read` and
   `lseo_publish_heading`; it cannot edit via core REST endpoints.
3. Create a dedicated user with that role and a revocable application password.
   Application passwords inherit user permissions; do not use an administrator.
4. Configure `LSEO_INSTANCE` (independent unique installation string),
   `LSEO_ENVIRONMENT` (`production`, `staging`, or `local`), `LSEO_USER_ID` (integer)
   and `LSEO_PAGE_IDS` (explicit integer array) in protected host configuration.
   There is no app route to broaden this allowlist. Staging clones require a new
   installation ID, separate user/password and deployment evidence.
5. Enter credentials only in the app's password control. They are stored in the
   explicitly checked Windows Credential Manager backend under
   `LocalSEOAudit.WordPress.v1`, separate from Google. There is no plaintext or
   environment-variable production fallback. SQLite stores only generated vault
   references. Requests disable ambient proxies/.netrc, redirects and automatic
   retries, pin public addresses on hosted connections, and never log HTTP errors
   containing credentials. Revoke unused application passwords at the host.

An existing Elementor/SEO-plugin production site will be rejected by version 1.
Do not remove production plugins, alter templates or change excerpts just to make
it pass. Extend the adapter in a separately reviewed change with representative
fixtures, exact CMS mappings and additional effect/rollback contracts.

## Reproducible local validation

Only synthetic data is used. The database is ephemeral, bound inside the Compose
network; WordPress listens only on `127.0.0.1:8879`. Test bootstrap creates random
temporary passwords inside the container. The Python test captures application
credentials in memory, never prints or persists them. The fixed database password
in Compose is deliberately synthetic and must never be reused elsewhere.

```powershell
docker compose -p lseo-publishing-test -f wordpress/compose.test.yml up -d
$env:LSEO_WORDPRESS_TEST = '1'
.venv-mvp/Scripts/python.exe -m unittest tests.test_wordpress_integration -v
.venv-mvp/Scripts/python.exe -m unittest tests.test_publishing -v
docker compose -p lseo-publishing-test -f wordpress/compose.test.yml down -v
```

Use your configured Python environment in place of `.venv-mvp` if needed.
The integration suite includes real writes, server duplicate suppression, concurrent
conflicts (including a two-connection navigation race while waiting for the page
lock), literal entity-looking text, byte/metadata preservation, rendered verification, inverse rollback,
wrong-instance/object/field rejection and minimal-account permissions. Synthetic
app tests cover stale revisions, authority, workspace lock, timeouts, explicit
reconciliation/resume, partial batches, verification failure and restoration.

## Plan for separately approved live validation

1. Select the exact site/audit and inspect its real CMS/editor/plugins read-only.
   Record compatibility or a precise unsupported result. Do not infer field IDs
   from public selectors. No production editor/autosave session is needed.
2. Verify a truly isolated staging clone. Obtain separate approval for any host
   setup/plugin installation effects before performing them. Confirm core/theme
   checksums, page excerpt, allowlists, credentials and no live services/jobs.
3. Prepare one reversible heading action, human-confirm its facts, refresh/freeze,
   review CMS/public evidence and run the staging apply/verification/rollback flow.
   Inspect layout manually and retain journals, hashes and page captures.
4. For production, present a new packet with exact URL, page/block/anchor, old/new
   wording, factual source, current validation, server side effects and rollback.
   Wait for the human's exact approval and Apply instruction. Staging approval or
   code/PR approval never substitutes for that permission.
5. Apply one action, reconcile any uncertainty before retry, verify raw CMS plus
   rendered adjacent content/directives and inspect appearance manually. Report
   write and verification independently. Expand scope only after fresh review.

## Official references consulted

- [WordPress REST posts](https://developer.wordpress.org/rest-api/reference/posts/)
  distinguishes title/content fields; it is not a conditional publication contract.
- [Core heading block](https://developer.wordpress.org/block-editor/reference-guides/core-blocks/#heading)
  and [parse_blocks](https://developer.wordpress.org/reference/functions/parse_blocks/)
  define the block data inspected by the adapter.
- [REST route permission callbacks](https://developer.wordpress.org/reference/functions/register_rest_route/)
  and [application passwords](https://developer.wordpress.org/advanced-administration/security/application-passwords/)
  inform the separately scoped authentication mechanism.
- [Yoast REST API](https://developer.yoast.com/customization/apis/rest-api/) is
  read-only; changing a rendered SEO title through that response is unsupported.
- [Elementor data structure](https://developers.elementor.com/docs/data-structure/)
  documents separate serialized metadata. It must not be overwritten as ordinary
  WordPress block content.
