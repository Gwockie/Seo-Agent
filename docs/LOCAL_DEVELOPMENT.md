# Active workflow: keep StartUp and work locally

The owner chose to retain the reported SiteGround StartUp plan and defer the quoted
$13/month ($156/year) upgrade. Work begins with read-only evidence and local drafts.
No hosting upgrade, remote staging account or SSH credential is needed for that work.

Public site: https://meadowandmindpsychology.com/
Active theme: Hello Elementor (owner reported). Theme/PHP/plugin versions, any child
theme and Elementor Free/Pro availability still need inspection.

## 1. Build the read-only baseline

Use the existing audit workflow in `README.md` and `AGENTS.md`. Search Console
requires the owner's authorized Desktop OAuth file and consent, with only
`https://www.googleapis.com/auth/webmasters.readonly`. Never broaden scopes.

```powershell
.\.venv\Scripts\python.exe -m seo_agent sites
```

Select the exact accessible property returned; do not assume a domain property exists.
Then run the 90-day snapshot using that verified property and the public URL:

```powershell
.\.venv\Scripts\python.exe -m seo_agent snapshot --site "EXACT_PROPERTY_FROM_SITES" --url "https://meadowandmindpsychology.com/" --days 90 --inspect
```

If GSC access is unavailable, document the gap and continue public-page inspection
read-only. Do not invent query impressions, rankings or index-inspection results.
Create the executive summary, recommendations and proposed edits under ignored
`reports/<snapshot>/` as required by `AGENTS.md`.

Collect comparable public mobile page/asset and response-time evidence. Separate
theme/Elementor/plugin/front-end issues from possible server constraints. No hosting
bottleneck or upgrade performance benefit has yet been established for this site.

## 2. Prepare code and content locally

- `src/schema/`: confirmed JSON-LD facts, strict syntax checks and semantic validation.
- `src/optimization/`: small patches justified by actual enqueue/dependency evidence.
- `src/templates/`: local-intent content/templates compatible with Hello Elementor.
- `src/theme/`: integration proposals against inspected source, preserving parent code.

Use the matching prompt under `prompts/`. Keep clinical factual confirmations and
private evidence under ignored reports. A full WordPress clone is not required for
the audit, content proposals or initial schema drafting. Do not prepare integration
patches against imagined theme files or assume JSON parsing proves schema eligibility.

Validate each draft appropriately. Local PHP matching the site's major/minor version
is needed for `php -l` and runtime tests; PHP is not installed by this scaffold.
Once a JSON draft exists, a basic syntax check can be run locally:

```powershell
.\.venv\Scripts\python.exe -m json.tool src/schema/localbusiness.json
```

Review diffs and tests without creating a staging deployment package. The existing
`prepare_staging.py` expects an actual declared staging target and is deferred.
Leave `SG_STAGING_*` identities unset; localhost and production are not substitutes.

## 3. Add an isolated local WordPress copy when runtime tests require it

No WordPress clone/runtime has been installed yet. Before building one:

1. Inspect the actual WordPress/PHP/theme/plugin versions and choose a compatible
   local runtime. Keep WordPress files under `local/wordpress/` and runtime configuration
   under `local/runtime/`; these remain ignored rather than becoming deployable source.
2. Obtain necessary source and sanitized exports through authorized read-only routes.
   Do not install a production export/staging plugin or trigger production write jobs.
   Exclude patient records, real form submissions and unnecessary uploads. Keep any
   local exports/backups under ignored `local/backups/` with limited access.
3. Give the local copy its own database and local URL. Before starting WordPress,
   remove production database credentials and isolate outbound connections. Prevent
   live email, booking, payments, analytics and form side effects; then inspect the
   clone's configuration/plugins. Synthetic test data is sufficient.
4. Test schema rendering, Elementor layouts, script dependencies, menus and forms
   locally. Record runtime limitations and remaining remote checks. Local results
   do not demonstrate production server speed or Google indexing behavior.

Normal local file preparation is authorized; this setup creates no external website
changes. Production writes remain prohibited. Any future staging website write still
needs explicit approval of its exact actions, current/proposed values and rollback.

## 4. Revisit paid staging only when justified

Record the decision evidence first: repeated server latency/resource limits under
comparable conditions, or frequent staging tasks whose setup/testing time makes the
additional recurring cost reasonable. Separate server processing from front-end
bottlenecks before making a hosting recommendation.

If the owner later chooses remote staging, use `STAGING_SETUP.md` and `deploy/README.md`.
Verify the actual installation, paths, current values, backups and an exact approved
release. No purchase, remote provision, uploader activation or production promotion
is implied by this local-first workflow.
