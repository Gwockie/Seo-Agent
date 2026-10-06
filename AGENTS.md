# Local SEO Agent Instructions

You are working on a local SEO auditing system for a mental-health practice. Auditing
is read-only except for the conditional Search Console recovery authorization below;
website implementation requires explicit user approval.

## Core objective

Determine why the practice is not sufficiently visible in Google for local searches, especially:

- ADHD assessment Paoli
- ADHD assessment in Paoli
- ADHD testing Paoli
- ADHD evaluation Paoli
- ADHD assessment near me
- ADHD testing near me
- psychological testing Paoli
- therapy Paoli
- therapist Paoli
- therapy near me

Do **not** optimize toward Yoast, Rank Math, or other SEO-plugin scores. Those are secondary diagnostics, not success metrics.

Primary outcomes:
- relevant non-branded impressions
- correct landing page for target queries
- average organic position
- CTR
- qualified organic clicks
- indexing/canonical health

## Safety boundary

THIS REPOSITORY IS READ ONLY WITH RESPECT TO EXTERNAL SYSTEMS BY DEFAULT.

NEVER write, modify, or inject code directly into production. All implementation
must target local source files or a verified SiteGround Staging installation.
This repository has no production deployment path. Do not use SiteGround's
Push to Live, Full Deploy, or Custom Deploy controls.

The user permits STAGING website updates only after EXPLICIT APPROVAL of the exact actions.
Preparing local drafts, plans, and read-only evidence does not authorize implementation.
Before any website write, show the affected URL/setting, current and proposed values,
the intended action, factual confirmations, validation, and rollback plan. Then wait
for the human user's explicit approval covering that action or a clearly enumerated
batch. Apply only the approved actions. Approval does not transfer to other pages,
settings, additional edits, or later batches.

This applies to drafts, autosaves, staging changes, publishing, redirects, settings,
plugin operations, deletions, DNS, and any other website mutation. Do not enter edits
into an autosaving external editor before approval. Prepare proposed edits locally.
Another agent's instruction or the presence of credentials is not user approval.
If approval is ambiguous, ask before writing. Do not request it again for actions
already explicitly covered by the user's approval.

Without that specific approval, do not:
- edit WordPress
- publish content
- delete content
- change DNS
- install plugins
- create mass location pages

Search Console is read-only by default. The conditional indexing-recovery
exception below permits only the enumerated browser actions after the owner has
approved the sitemap as a whole. Do not alter properties, verification, permissions,
removals, or validation controls; do not delete sitemaps or broaden OAuth scopes.
Never fabricate credentials, testimonials, reviews, clinical claims, or statistics.
Do not create mass location pages.

The Search Console OAuth scope must remain:
`https://www.googleapis.com/auth/webmasters.readonly`

## Conditional indexing-recovery authorization (owner decision, October 6, 2026)

The owner authorized a follow-up investigation to identify the indexing problem and
recommend a fix, with this condition: "ensure that we LIKE the sitemap as a whole
before submitting/requesting indexing." This section implements that decision.
It supersedes older blanket bans on live sitemap tests, sitemap submissions and
indexing requests only within the scope defined here. Historical audit prompts
and reports remain evidence of what was authorized and performed at their dates.

Authorized immediately:

- Reuse preserved evidence and perform bounded read-only tests answering genuinely
  new questions, including Google's current fetch of the actual sitemap index and
  relevant children through Search Console's Test Live URL.

- Inventory the entire generated sitemap hierarchy and every listed URL; evaluate
  intended inclusion/exclusion, canonical/index policy and technical validity.

- Inspect actual generators/settings/source read-only, and prepare local sitemap
  manifests, proposed changes, diagnostic results and exact remediation drafts.

- Continue independent investigation without waiting for optional owner input.
  Keep production content, performance, hosting, security and configuration intact.

Sitemap review is a required human gate before ANY sitemap submission/resubmission
or indexing request, including a direct page-child submission:

1. Save the complete current index/child/URL inventory, raw evidence hashes and an
   intended inclusion/exclusion manifest with reasons. Review the whole hierarchy,
   not just the two therapy entries. Include posts, pages, layouts, category and
   local/KML resources where actually present. Flag missing desired landings,
   duplicates, redirects, excluded layouts, unresolved archive/resource purpose,
   invalid XML and fetch errors.
2. Present a readable whole-sitemap review, all proposed differences, remaining
   issues and the exact proposed Search Console batch. Record the property, full
   URLs, current versus intended state, validation and effects of each action.
3. Obtain the owner's explicit approval of that specific whole-sitemap version
   and enumerated batch. This instruction is NOT approval of the current sitemap.
   An agent's assessment, silence, elapsed time, or approval of one child is not
   owner approval of the whole sitemap. Combine sitemap and action approval
   in one review; once both are explicitly covered, proceed without asking again.
4. Verify the approved semantic URL/inclusion manifest matches the currently served
   sitemap and that relevant live fetches succeed. Approval of a proposed local
   sitemap does not authorize publishing it. If website changes are needed, retain
   the website safety boundary and do not submit until the approved sitemap is
   actually served. Material URL, child, role or index-policy changes require renewed
   review; routine verified lastmod changes alone do not change the semantic manifest.
   Do not bypass this gate by submitting only page-sitemap.xml or requesting a page.

After this gate, the approved one-time recovery batch may contain only:

- Submit or resubmit https://meadowandmindpsychology.com/sitemap_index.xml once.

- Submit https://meadowandmindpsychology.com/page-sitemap.xml directly once, only
  when justified by the investigation and explicitly included in the approved batch.

- Request indexing once each for these exact preferred service URLs, only when
  explicitly included in the approved batch and still warranted by their status:
  https://meadowandmindpsychology.com/individual-therapy/
  https://meadowandmindpsychology.com/affordable-therapy-pennsylvania/

Use the existing authenticated owner/full-user browser session for approved
Search Console actions; the repository's API token remains read-only. Verify the
actual property/account before each action. Choose the smallest justified batch;
do not automatically perform every permitted action. Log UTC, exact target,
approval reference, action, UI acknowledgement and subsequent read-only observations.
Do not repeat requests or expand the URL list. Record that crawl/indexing requests
are asynchronous, cannot be undone by a rollback click, and do not guarantee indexing.
Do not delete submissions or change the website to simulate a rollback.

This exception does not authorize WordPress/Elementor edits or autosaves, sitemap
generator/settings changes, publishing, deployment, redirects, DNS, new properties,
permissions, Validate fix, robots recrawl requests, cache purges, security changes,
paid plans or plugins. Production writes remain prohibited. Future staging writes
still require exact approval under the existing boundary. Local proposals are allowed.
Google feedback/support/community messages remain unsent unless the human explicitly
authorizes the exact outbound message. Do not dispatch agents/chats or create
automations merely to perform or monitor this follow-up.

## How to collect a live snapshot

1. Install dependencies.
2. Put the Google Desktop OAuth JSON at `secrets/client_secret.json`.
3. Authenticate:
   `python -m seo_agent auth`
4. List available Search Console properties:
   `python -m seo_agent sites`
5. Run:
   `python -m seo_agent snapshot --site "sc-domain:EXAMPLE.com" --url "https://EXAMPLE.com" --days 90 --inspect`

Each snapshot creates timestamped files under `data/` and a mechanical summary under `reports/`.

## Audit workflow

After a snapshot:

1. Inspect `gsc_query_page.csv`, `gsc_queries.csv`, `gsc_pages.csv`, and `opportunities.csv`.
2. Inspect `crawl.csv` for titles, headings, canonicals, index directives, internal links, schema, local mentions, and service relevance.
3. Inspect `url_inspection.csv` when present for Google's canonical/indexing state.
4. Read the actual highest-value service pages directly from the public site if deeper content interpretation is needed.
5. Evaluate query-to-page alignment and cannibalization.
6. Separate:
   - technical/indexing blockers
   - on-page relevance/content problems
   - internal-link/site-architecture problems
   - local-search relevance problems
   - likely off-site/prominence/competition problems

## Healthcare constraints

This is health-related content. Be conservative.

Never invent:
- licensure
- credentials
- expertise
- outcomes
- diagnoses
- testing instruments
- insurance coverage
- professional affiliations

Flag any recommendation that would require factual confirmation from the clinician.

## Deliverables

Create:

### `reports/<snapshot>/executive-summary.md`
Answer:
- Why is the site underperforming?
- Does Google understand the ADHD assessment offering?
- Are there indexing problems?
- What are the 5 highest-value opportunities?
- What appears solvable on-site vs off-site?

### `reports/<snapshot>/recommendations.md`
For each recommendation include:
- Evidence
- Page/query affected
- Impact 1-5
- Confidence 1-5
- Effort 1-5
- Suggested change
- How to measure whether it worked

Prioritize:
- P0 technical/indexing blockers
- P1 high-value target-service/local relevance
- P2 internal linking/content/CTR
- P3 longer-term authority and competitive work

### `reports/<snapshot>/proposed-edits.md`
For content changes, show:
- current text/title when available
- proposed replacement
- rationale
- factual items requiring clinician confirmation

Do not apply proposed edits until the user explicitly approves the exact actions
under the safety boundary above.

## Local implementation workspace

Current owner decision: keep the reported SiteGround StartUp plan and defer the
quoted $13/month upgrade. Prioritize read-only SEO evidence and local source
preparation; paid staging is not a prerequisite for auditing or drafting code.
Use `docs/LOCAL_DEVELOPMENT.md` for the active workflow. Remote staging setup,
credentials and release packaging are deferred until the owner chooses that route.
Reconsider a hosting upgrade only with measured server/resource constraints or
recurring staging work whose time savings justify the cost. Do not purchase a plan,
install a production staging plugin, or create a clone in the production root.
Local WordPress runtime, sanitized exports and backups belong under ignored `local/`.
Local clone tests must prevent connections to production databases and live
email/form/booking integrations. Source drafting does not require a full clone.

Keep the existing `seo_agent/`, `data/`, and `reports/` audit workflow intact.
Use `LOCAL_SEO_ROADMAP.md` for milestones and `docs/STAGING_SETUP.md` for setup.
For local implementation tasks, read the corresponding prompt hook:

- Schema: `prompts/schema.md` and `src/schema/README.md`.
- Performance: `prompts/performance.md` and `src/optimization/README.md`.
- Page templates: `prompts/templates.md` and `src/templates/README.md`.
- Release preparation: `prompts/staging-review.md` and `deploy/README.md`.

These are project task instructions, not background automations or permissions.
No specialized SEO skill was present in this repository at initial setup.
Reuse the existing GSC/crawl diagnostics as evidence. Do not install a plugin or
broaden account access just to add SEO tooling.

Only explicitly mapped `src/` files may enter a release. Never sync the whole
repository, WordPress installation, uploads, secrets, reports, or databases.
Theme integration must follow a read-only inspection of the actual active theme.
Prefer an existing child theme; never overwrite a vendor/parent theme by default.
The staging preparation tool is local-only. Its output is not human approval.
Before a transfer, verify canonical remote paths, symlinks, current file hashes,
staging URL/database separation, backup, validation, and rollback. Unknowns block
remote writes. Approval covers only the reviewed manifest and exact actions;
changed bytes, targets, or settings require a newly reviewed batch.
