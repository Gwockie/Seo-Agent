# Local SEO development roadmap

Prepared October 5, 2026. This checkout is linked to `Gwockie/Seo-Agent` on GitHub.
Public site: https://meadowandmindpsychology.com/ (owner supplied; homepage reachable).
Active theme: Hello Elementor (owner reported; version and child-theme status unverified).
Hosting: SiteGround StartUp (owner's tentative report; account tier still to confirm).
PHP version, plugins/Elementor subscription and clinical facts still require
verification. Remote staging identity and physical paths are deferred.

SiteGround's current [WordPress plan comparison](https://www.siteground.com/wordpress-hosting.htm)
lists SSH on StartUp, but built-in staging begins with GrowBig. The owner chose to
keep StartUp for now and defer the quoted $13/month ($156/year) upgrade. Begin with
read-only auditing and local source preparation using `docs/LOCAL_DEVELOPMENT.md`.
A local WordPress copy can support runtime tests when needed; it is not required
to start the audit or draft schema/content. No hosting bottleneck has been measured.
Revisit GrowBig only if server/resource evidence or recurring staging work justifies
the cost. No plan purchase, plugin installation or manual production-host clone is
authorized. The SFTP destination stays unset and transfer disabled until an actual
staging installation exists and a concrete batch receives exact human approval.

Hello Elementor requires an Elementor-aware implementation: inspect rendered widgets,
Elementor/plugin assets and page/template assignments as well as theme enqueue code.
Do not edit the parent theme. Child-theme creation/activation on staging requires
an exact reviewed batch. Elementor template JSON belongs in the local template
workspace; importing/assigning it in WordPress is separate from SFTP code transfer.

## Architecture

```text
seo-agent/
  AGENTS.md                    Project instructions and production prohibition
  LOCAL_SEO_ROADMAP.md          Milestones and acceptance criteria
  seo_agent/                   Existing read-only GSC and public crawl tool
  tests/                       Audit and release-preparation validation
  src/
    schema/                    Proposed JSON-LD source
    optimization/              Reviewed enqueue/performance changes
    templates/                 Reusable local-intent WordPress templates
    theme/                     Reviewed child-theme integration files
  prompts/                     Evidence-driven task and review hooks
  docs/LOCAL_DEVELOPMENT.md     Active StartUp/local workflow
  docs/STAGING_SETUP.md         Deferred SiteGround/SSH setup
  deploy/                      Environment-based configuration and disabled uploader
  scripts/prepare_staging.py    Local package validation and manifest generation
  data/                        Private audit evidence (ignored)
  reports/                     Private audit reports and proposed edits (ignored)
  secrets/                     Local OAuth files (ignored)
  local/                       Local WordPress runtime/exports/backups (ignored)
  dist/                        Local release payloads and reviews (ignored)
```

Only explicitly mapped website source files enter a release. Documentation is not
uploaded. Existing theme code must be inspected/downloaded read-only before an
integration decision. Work in an existing child theme if compatible. Creating or
activating a child theme on staging is a separately approved action. WordPress
files, database dumps, private forms/patient data and credentials do not belong in Git.

## Milestone 0 — read-only evidence and local setup

- Follow `docs/LOCAL_DEVELOPMENT.md`; retain StartUp and defer remote staging setup.
- Inventory WordPress/PHP/theme versions and existing schema/caching plugins.
- Run an authorized read-only 90-day GSC snapshot and public crawl; produce the
  executive summary, recommendations and proposed edits required by `AGENTS.md`.
- Record target query-to-page mapping and current indexing/canonical state before
  deciding what to implement. Keep GSC OAuth at `webmasters.readonly`.
- Inspect public mobile behavior, asset requests and server response measurements
  before attributing any performance issue to the hosting tier.
- When runtime testing is needed, plan an isolated local WordPress copy from authorized
  read-only source/exports. Keep runtime data under ignored `local/`, minimize sensitive
  records and disable live database/email/form/booking connections before running it.

Acceptance: an evidence-based query/page and mobile baseline, a list of unresolved
facts and a prioritized local implementation plan. Missing GSC access is explicitly
reported; public crawl evidence can still be reviewed. Hosting upgrades and remote
staging credentials are not prerequisites. No remote writes occur.

## Milestone 1 — accurate LocalBusiness JSON-LD

Use `prompts/schema.md`. Prepare `src/schema/localbusiness.json` and a local
integration proposal under `src/theme/` after inspecting existing schema output.

Confirm the exact practice name, public address, phone, canonical URL, services,
clinician credentials, hours and eligible service area with the clinician. Select
the most specific truthful Schema.org type; do not infer physician status or an
ADHD-testing service from a target keyword. Unknown optional fields are omitted.
Use consistent entity IDs and relate confirmed services to the practice where
appropriate. Avoid competing plugin/theme entities and invented reviews/ratings.

Acceptance: strict JSON parsing, Schema.org validation, Google's Rich Results Test
in code mode where applicable, no unresolved factual claims, and one consistent
entity graph matching visible content. A local PHP loader must encode safely and
render exactly once on intended local test pages when a clone is available. Remote
staging rendering remains a deferred check after an exact approved release. Uploading
the JSON file alone does not add structured data to the site. Google eligibility
and ranking gains cannot be promised; see [Google's LocalBusiness guidance](https://developers.google.com/search/docs/appearance/structured-data/local-business).

## Milestone 2 — active-theme script audit and mobile performance

Use `prompts/performance.md`. Inspect downloaded theme code and dependencies locally,
including Elementor/widgets/add-ons rather than attributing all cost to Hello;
record script handles, source, dependencies, page scope, loading strategy, inline
configuration and associated plugin. Collect a read-only mobile baseline for home,
ADHD assessment and therapy pages, including waterfall/render blockers, LCP, INP
field evidence when available, CLS and lab diagnostics. Lighthouse is a diagnostic,
not the primary outcome; lab blocking-time measurements are not field INP.

Draft small justified changes in `src/optimization/`. Preserve forms, booking,
consent, menus and accessibility; do not blindly dequeue jQuery or blanket-delay
scripts. Coordinate with the existing optimizer to avoid duplicate optimizations.

Acceptance: local syntax/dependency checks, functional tests in an isolated local
clone when available, and repeated comparable mobile measurements. Any local/server
timing differences must be documented; a local result does not prove faster hosting.
Remote staging validation is deferred until provisioned and approved. Protected staging
may not have CrUX field data; use controlled lab checks there. Document changes in
behavior and bytes/requests as well as lab performance. Production field verification
is a later read-only measurement, contingent on an independently managed release.

## Milestone 3 — local-intent page templates

Use `prompts/templates.md`. Design one reusable template around confirmed services
and the real Paoli location. Map ADHD assessment/testing/evaluation queries to an
appropriate existing primary service page where evidence supports that intent.
Plan separate therapy content only where the service and search intent differ.

Create drafts in `src/templates/`, with reviewed integration in `src/theme/`.
Include accessible headings, service/process/location information, clinician-
confirmed eligibility, a useful contact route, and relevant internal links.
Templates must fit the installed classic/block theme and page builder; determine
that first. Hello Elementor is owner reported: inspect the actual Elementor layout,
Free/Pro availability and existing templates before choosing PHP or Elementor JSON.
Keep Elementor template exports/proposals local for a separately approved staging
import and assignment. SFTPing their JSON into a theme does not apply an Elementor
layout. A template upload alone does not create a WordPress page or assign it.
Page creation/assignment, metadata, canonical and internal-link edits each require
exact approval on staging. No mass town pages, keyword stuffing or false offices.

Acceptance: correct query-to-page alignment, useful unique local drafts, accessible
mobile layout, compatible local rendering when a clone is available, deliberate
canonical behavior and factual signoff. Remote imports/assignments remain deferred.

## Release and measurement gates

Active local loop: audit evidence -> prioritized local patches -> syntax/semantic
checks -> isolated local runtime tests when needed -> reviewable diffs and findings.
This loop requires neither paid staging nor a completed deployment manifest.

The following remote release gates apply only if the owner later chooses staging:

1. Local code + existing evidence -> syntax/semantic checks -> explicit file mapping.
2. `prepare_staging.py` -> hashed local payload + manifest + filled-in review.
3. Show current/proposed code/settings, affected URLs, clinical confirmations,
   tests, exact ancillary actions and a staging-only rollback plan to the owner.
4. Wait for explicit human approval of that batch. Implement the disabled transfer
   placeholder only with verified paths and preflight checks; upload only that batch.
5. Validate staging output, mobile behavior, forms with synthetic data, logs and hashes.

Production writes and SiteGround Push to Live are prohibited for this agent/project.
There is no production promotion workflow. The owner may independently arrange a
production release outside this pipeline; staging work alone changes no production
rankings. If a production release occurs, measure target non-branded impressions,
landing-page alignment, organic position, CTR, qualified organic clicks and canonical/
index health over comparable periods. Separate seasonality and demand from implementation
effects. Do not optimize for SEO-plugin scores or submit indexing/sitemap changes.
