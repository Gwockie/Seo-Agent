# Site-specific hosting and CMS discovery

Use **Hosting & CMS** in the app to configure an environment once, refresh bounded
read-only evidence, import protected administrator inventory, and review saved
compatibility. Setup is independent of the publication destination, credentials,
proposal approval, CMS approval and Apply controls. Nothing here installs a plugin,
creates a host account, changes permissions, enters an editor, or enables publishing.

## Setup and collection

1. Select the site's app-validated profile. Add a named discovery environment and
   its hosting provider (Unknown is allowed), production/staging/local designation,
   and exact canonical CMS home URL ending in `/`. Production must match the
   selected profile; staging must be separate. Hosted access requires TLS and public
   address validation; local synthetic tests require loopback HTTP. Unsupported
   encoded paths, query-bearing homes and redirects are rejected.
2. Choose **public**, **wordpress_rest**, or **administrator_export**. Public and
   export modes need no credential. REST access uses a separate username and
   application password entered only in the app password control. Use existing
   authorized access; discovery does not create or broaden host access. An
   application password inherits its account's permissions and is not intrinsically
   read-only. Missing privileges remain missing evidence.
3. Leave installation identity blank until the administrator supplies an independent
   stable host/CMS identity. The generated app connection ID is never substituted.
   An entered/exported installation ID is recorded as **administrator asserted**;
   ordinary WordPress REST does not prove it. Credential rotation preserves the
   installation and evidence scope for identical configuration. Changed URL,
   environment, identity, provider/access configuration or site profile invalidates
   affected evidence. Separate clones need separate installation identities.
4. Select the saved environment and **Refresh read-only discovery**. Leave page IDs
   blank to list at most 20 public REST page identities. Enter up to 10 explicit
   page IDs to capture their REST identity and rendered widget structure. Only
   public published pages are eligible. Public generators/theme/plugin asset names
   are inferred clues, never an authoritative active inventory.
5. REST mode additionally requests those pages with `context=edit` and explicit
   fields for raw content/excerpt and template. It tries the existing core plugins
   and themes GET endpoints with only name/version/status fields. These may be
   denied, filtered or incomplete. It does not request user records, settings,
   arbitrary options or private Elementor metadata. Use a sanitized administrator
   export for missing inventory, actual metadata row IDs and host effects.

Requests disable proxies, `.netrc`, cookies, redirects and automatic retries.
Hosted sockets use the public-address-pinning adapter with TLS verification. Each
response is bounded to 2 MiB and a checked 20-second streaming budget (15-second
socket read timeout); a reader has 48 requests and a checked 90-second overall
budget. The finite socket timeout can extend a time check until the next chunk or
request completion. Requests are explicit, not background refreshes. Read responses
are projected onto the allowed schema, not stored as arbitrary API objects.

Authenticated GETs may update host access logs and application-password last-used
time/IP bookkeeping. No save hooks, autosaves, cache flushes, updates or setup
routines are deliberately invoked. Arbitrary host/plugin behavior still needs
independent host evidence; HTTP GET alone cannot certify that a host has no effects.

## Protected administrator export

The import UI accepts a path to an existing owner-protected local `.json` file,
at most 2 MiB. It rechecks folder protection, rejects duplicate JSON keys, unknown
schema fields, wrong scope, future/naive dates, duplicate page/metadata identities,
credential-bearing keys/URLs and common secret formats. Never provide an SQL dump,
options export, customer submissions, user/account records or credentials. Free
text and raw page content must be sanitized by the administrator: automatic
screening cannot identify every possible secret disguised as ordinary prose.
The original source file is neither copied to the repository nor included in backups.

**Write an empty scoped administrator template** saves a new file to a protected
directory. It includes the exact selected site ID/URL, profile hash, CMS URL,
environment and installation ID; all must match on import. Populate it from
already authorized host evidence without making production changes. A template's
timestamp is only a placeholder; replace it with the actual evidence collection
time. Imports retain collection time, import time, source reference, SHA-256 of the
original bytes and a canonical evidence hash. They remain administrator assertions,
including after export/restore. An imported claim cannot set certainty to confirmed.

Example evidence sections (use the scope from the app-generated template):

```json
{
  "software": [
    {"kind": "core", "name": "WordPress", "version": "observed-version"},
    {"kind": "plugin", "name": "elementor", "version": "observed-version", "active": true}
  ],
  "complete_inventory": ["core", "plugin", "mu_plugin", "dropin"],
  "pages": [{
    "id": 9001,
    "url": "https://example.com/service/",
    "type": "page",
    "status": "publish",
    "template": "default",
    "raw_content": "Sanitized exact page content",
    "raw_excerpt": "Exact explicit excerpt, or an empty string if actually empty",
    "metadata": [{"row_id": 42, "key": "_elementor_data", "value": "[]"}],
    "shared_ids": []
  }],
  "host": [{
    "area": "database",
    "result": "isolated",
    "production_resource": "production-database-reference",
    "environment_resource": "separate-staging-database-reference",
    "observation": "Administrator evidence describes separate databases and access boundaries.",
    "source_reference": "Host evidence ticket or protected document reference"
  }]
}
```

Software kinds: `core`, `php`, `database`, `table_engine`, `theme`, `plugin`,
`mu_plugin`, `dropin`. Each supports a name, version, optional active status and
SHA-256. `complete_inventory` explicitly records inspected categories including
empty MU/drop-in lists; omission means unknown. Up to 300 software items and 20
published page/template records are accepted. Raw content is optional (null means
missing); raw excerpt distinguishes missing from explicitly empty. Template types
also include `elementor_library`, `wp_template`, `wp_template_part`. Only metadata
keys `_elementor_data`, `_elementor_page_settings`, `_elementor_edit_mode`,
`_elementor_version`, `_wp_page_template` are accepted. Actual numeric metadata row
IDs must come from administrator evidence; they cannot be inferred from HTML.
Nested credential-bearing settings are rejected even inside JSON strings.

For `table_engine` entries, `name` is the exact database table name and `version`
is its observed engine. Set `table_role` to `posts`, `postmeta`, `options` or
`journal` only after independently identifying that table's role in the selected
live WordPress installation. Each role can occur once. For example:
`{"kind":"table_engine","name":"site_posts","version":"MyISAM","table_role":"posts"}`.
Older exports without roles remain valid evidence but cannot satisfy this
publisher prerequisite. A server default, suffix match or another installation's
tables cannot fill missing identities. Roles are administrator assertions, not
runtime certification.

Within an Elementor `__dynamic__` binding dictionary, discovery also accepts the
exact `post-title` and `post-url` tag forms with a seven-character lowercase hex ID
and empty URL-encoded settings (`%7B%7D`, case-insensitive hex digits). It preserves
these strings as inert evidence. Unknown tags, nonempty/double-encoded settings,
extra attributes and malformed bracket strings remain rejected. This exception
does not evaluate tags or enable publishing: the static-heading mapper continues
to reject dynamic targets. Metadata row IDs still require independent evidence.

Host effect areas are `cache`, `mirrors`, `rendering`, `save_lifecycle`, `experiments`.
Use `result: observed` with the concrete observation and source reference; unknown
facts remain `unknown`. Do not alter production plugins, templates or cache settings
to fill gaps or to fit the current publisher.

## Isolation and compatibility

The separate [saved-action candidate workflow](actual-stack-validation.md) binds
offline Elementor preparation to an existing audit action and latest revision.
It reports missing evidence and unsupported targets without creating approval or
loosening the pinned publishing contract.

Isolation areas are `database`, `files_uploads`, `editor_settings`, `deployment`,
`installation_identity`, `access_identity`, `no_sync`, `no_jobs_webhooks`,
`no_customer_messages`, `restricted_access`, `noindex`. Each needs a concrete
observation and source reference, plus distinct production/environment resource
references. For negative conditions, refer to the independently inspected service
configuration/policy for each environment, not invented resources or secrets.

An import or checkbox alone cannot establish isolation. The UI first requires
current evidence for every condition, then a human must independently review those
host records and explicitly record their review source. It reports **human reviewed
isolation**, not machine-certified host isolation. Missing, conflicting, stale,
replaced or unreviewed evidence keeps work local. This record never automatically
enables an editor, publishing destination or approval.

Keep a connected production discovery environment with its independently obtained
installation ID. The `installation_identity` fact must use that exact ID as its
production resource and the selected staging ID as its environment resource. They
must differ. Conflicting production IDs, unknown identities or merely descriptive
resource labels cannot establish isolation. Reconfiguring or disconnecting the
production identity invalidates its prior isolation review.

Compatibility separates confirmed REST observations, inferred public clues,
administrator assertions, missing facts and stale/invalidated versions. Successful
evidence is retained after failures with its original age; attempt status is durable,
including interrupted runs. Evidence becomes stale after 24 hours. Reports retain
their original result and are recomputed for current freshness before use.

**Offline Elementor heading preparation** requires fresh imported metadata and a
separately collected public REST page with matching page ID, URL and template plus
a rendered capture. It checks the unique CMS widget, ancestors, document boundary,
heading type and literal text. Shared references, dynamic/global headings and nested
shared-document identity tricks remain rejected by the existing mapper. It saves
the actual metadata row assertion, exact widget path, source hashes, evidence IDs
and byte-preserving candidate JSON as a local version. Replaced source evidence
invalidates the mapping. HTML cross-checks do not prove a database metadata row ID;
that part remains administrator asserted.

Discovery results retain `publishing_compatible: false`. Separate publication
readiness distinguishes mapping, local validation, successful staging validation
and a current production review. The [Elementor adapter](elementor-publishing.md)
requires fresh independent endpoint checks against the exact local certificate,
current public/administrator evidence and an independent human host-effects review.
Imports or successful mapping alone never enable writing. See
[Elementor compatibility](elementor-publishing.md) and
[publication safeguards](wordpress-publishing.md).

The **Publisher host effects** panel requires all eight inventory categories and
concrete sourced observations for cache, mirrors, rendering, save lifecycle,
experiments, deployment and absence of production synchronization/jobs/messages.
The human must independently inspect provider/CMS records and record the source
of that review. Replacing either public or administrator evidence invalidates it.
The adapter cross-checks page/metadata identity, template, raw mirror/excerpt,
active plugin and exact runtime version/file-hash assertions with its own endpoint.
Use canonical plugin paths as inventory names; WordPress's hash is the sorted
`wp-includes` PHP tree, the theme/Elementor hashes cover their complete trees, and
the companion hash concatenates `elementor-publisher.php` then
`local-seo-publisher.php`. The manifest and endpoint verify the other core hashes.
No raw configuration, private options or passwords belong in the export.

The downloadable companion setup packet lists the deterministic package hash,
each file hash, destination, effects, validation and recovery. It is inert. Unknown
provider/installation values are explicit blockers; installing it on production
still needs separate exact approval. Discovery never installs it automatically.

## Storage, migrations and recovery

Credentials use only the explicitly validated Windows Credential Manager backend,
service `LocalSEOAudit.CMSDiscovery.v1`, independent of Google and publication
credentials. SQLite holds generated credential references and non-secret metadata.
No credential is exported or logged. Failure messages suppress underlying network,
vault and parser exception content. The app keeps the existing protected-workspace,
loopback-only launch and XSRF checks. Run it through `python -m seo_agent app`.

Schema 7 adds scoped connections, immutable versioned evidence and durable attempts
under the existing workspace operation lock. It preserves publication attempts and
uncertain-operation reconciliation. Site switching clears the previous site's
widget state; every connection/evidence operation independently checks site binding.

Protected history export is inert and is not an administrator import format.
Backups sanitize the database before archiving: credentials detached, discovery
disabled with new generations, discovery evidence marked history-only, publishing
still disabled and existing approval history inert. The backup copy uses secure
deletion and vacuum to exclude freed credential-reference bytes. Restore repeats
sanitization and validates evidence scope/hashes. Explicit reconnection, fresh
evidence and new publication approvals are required. No history becomes authority;
existing publisher journals remain available for read-only reconciliation.

## Official references consulted

- [WordPress REST pages](https://developer.wordpress.org/rest-api/reference/pages/)
  documents view/edit contexts, excerpt and template fields.
- [WordPress application passwords](https://developer.wordpress.org/advanced-administration/security/application-passwords/)
  documents inherited permissions and last-used bookkeeping.
- [WordPress plugins REST API](https://developer.wordpress.org/rest-api/reference/plugins/)
  and [themes](https://developer.wordpress.org/rest-api/reference/themes/) document
  the existing inventory routes; their availability depends on account access.
- [Elementor data structure](https://developers.elementor.com/docs/data-structure/)
  and [page settings](https://developers.elementor.com/docs/data-structure/page-settings/)
  describe separate JSON-backed page data and settings.

No specific host/provider is assumed. Provider inventory and isolation remain
administrator-sourced until an actual provider and authorized read route are known.

## Synthetic validation

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.venv-mvp/Scripts/python.exe -m unittest tests.test_discovery tests.test_discovery_ui -v
.venv-mvp/Scripts/python.exe -m unittest discover -s tests -v
```

The discovery HTTP fixture binds only `127.0.0.1` on an ephemeral port, uses synthetic
pages/credentials, exercises actual GETs and redirects, and closes automatically.
No live site, host plugin or production credentials are required.
