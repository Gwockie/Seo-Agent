# Keeping critical services discoverable and indexed

The new local command `python -m seo_agent.indexing_health` reads Google's stored ordinary index records for the two therapy URLs and the assessment control. It never submits a sitemap, requests indexing, changes the website, initiates new consent, schedules a job or sends a message. It requires the existing exact read-only OAuth scope and accessible practice property.

The check exits **0** only when all three critical URLs have a valid indexed verdict, successful ordinary recorded crawl, allowed robots/indexing states and exact matching user/Google canonicals. Exit **1** means a service is unknown, excluded, conflicting, incomplete or has regressed. Exit **2** means the check could not run; this is an observation failure, not a claim that the site is broken. A crawl older than another page's crawl is not treated as failure by itself.

From the repository root, use the existing authorized environment and run a bounded fresh check with a new output path:

```powershell
.\.venv\Scripts\python.exe -m seo_agent.indexing_health --live --out data\indexing-health-YYYYMMDDTHHMMSSZ
```

To compare with a prior healthy observation, add:

```powershell
--previous data\PRIOR_OBSERVATION\health.json
```

The previous file must have the same exact property and target set. Each run preserves full raw inspection responses, submitted/child sitemap metadata, the evaluated status and a concise Markdown report. Existing output directories are refused so evidence cannot be overwritten. Dates in raw records identify acquisition, distinct from Google's ordinary last-crawl timestamp.

An optional `--sitemap-dir DIRECTORY` checks a **locally acquired** complete XML hierarchy. Acquire it through the authorized read-only route, preserving status, headers, UTC and provenance. Do not bypass a robots/security denial to obtain it. The checker itself does no HTTP crawl. It rejects malformed XML, HTML challenge bodies, missing child files, wrong namespace/host/scheme, child paths that escape the supplied XML directory, duplicate primary entries, missing critical services and changed child/URL/image relationships against an earlier supplied hierarchy. Routine lastmod-only changes do not alter the structural digest. This structural digest is different from the reviewed semantic manifest, which additionally contains intended roles/index policies. The tool cannot infer new roles, page-response policy, or evidence freshness from XML alone.

`--replay PATH` can evaluate preserved raw evidence without network calls. It explicitly labels the result **historical_replay**. Replay results are suitable for validating the checker and tracing an older state; they never establish current recovery.

## Recovery acceptance

The intervention is complete only as a submitted request when Google's exact acknowledgement is saved. The indexing issue is recovered only after both therapy URLs report the preferred indexed state with ordinary crawl/canonical evidence. Save that first successful fresh observation as the recovered baseline. A later fresh observation must confirm the state persists. Continue measuring relevant non-branded query-to-page performance separately; being indexed does not establish ranking recovery.

The [October 6 recovery](audits/2026-10-06-indexing-recovery/README.md) was verified after one approved request per therapy URL. Perform bounded read-only persistence checks around **October 13 and October 20**, using the recovered baseline. These are observation dates, not promised indexing deadlines. Do not repeat the completed requests or send the earlier failure case as an unresolved complaint. If a later check exposes a regression, preserve its actual fetch, exclusion or canonical reason and propose the narrow corresponding correction. Sending a new case remains separately gated.

## Preventing an unnoticed recurrence

Use the command before declaring recovery, after relevant site changes and during routine SEO reviews. Require published service URLs to remain in the reviewed page sitemap, navigable from the home/FAQ/service navigation, HTTP 200, unprotected, crawlable, indexable and self canonical. Compare the complete sitemap with the owner-approved semantic manifest before any new submission or indexing batch. Retain true significant lastmod dates. Preserve the active embedded layouts when excluding their standalone discovery URLs.

When a future preferred service is published, include its exact URL in the explicit target set using repeated `--url` arguments, including the existing critical URLs and control. Start a new baseline for that expanded set; comparisons intentionally reject different target sets. Track a new page's pending indexing separately from an established page's regression, and do not declare its search launch complete until an ordinary preferred indexed record exists. A material sitemap expansion still needs whole-version review before any request. The checker never requests indexing automatically.

The new command catches loss of indexed status, canonical drift and missing sitemap relationships. It is a manual read-only guard, **not an active recurring monitor** and not a guarantee against Google's future selection decisions. AGENTS.md prohibits creating an automation merely for this follow-up. There is no approved production deployment path in this repository, and no website or hosting change is implied by the guard.

## Validation performed

Thirteen focused tests cover unknown URL rejection despite other passing results, preferred indexed success, canonical regression, discovered versus crawled exclusions, missing/invalid/future ordinary crawl evidence, missing targets, malformed/challenged/duplicate XML, Windows child path and resolved-path escapes, missing desired pages, lastmod-only stability, material sitemap drift, historical replay labelling, overwrite refusal, bounded read-only collection and prevention of new or broader consent. The checker also replayed actual dated practice evidence: it correctly failed both therapy URLs as unknown while passing the indexed assessment control.
