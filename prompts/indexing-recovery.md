# Continue indexing diagnosis: review the whole sitemap before recovery

> Completion notice, October 6, 2026: the whole existing sitemap was reviewed and
> approved as current-served-r2 for a bounded batch of one indexing request per
> therapy URL. Both requests were performed once; subsequent ordinary API/browser
> records verified both preferred URLs indexed with successful crawls and matching
> canonicals. See [the public-safe recovery summary](../docs/audits/2026-10-06-indexing-recovery/README.md)
> and AGENTS.md's completed recovery record. Do not rerun the completed batch or
> treat the pre-intervention unknown statuses below as a current failure. For a
> future regression, use the read-only health check and a named new diagnostic
> question under the current authorization gates. Raw evidence remains ignored.

Work in C:\Users\keyse\.codex\worktrees\6550\local-seo-agent.
Practice: https://meadowandmindpsychology.com/
Existing verified Search Console URL-prefix property:
https://meadowandmindpsychology.com/

Execute this follow-up, using the updated AGENTS.md authorization. Identify the
next discriminating facts and recommend the smallest supported fix. Do not restart
the October 5-6 investigation. Do not substitute another generic audit, checklist,
content rewrite or explanation that Google decides.

The owner's latest instruction is to allow the investigation to proceed, while
ensuring "we LIKE the sitemap as a whole before submitting/requesting indexing."
Prepare a concrete whole-sitemap review for the owner's approval. You may perform
the approved narrow Search Console recovery actions after that gate; you may not
approve the sitemap on the owner's behalf. No sitemap version or recovery batch
has been approved yet. This task does not authorize production website changes.

## Read this context first

Read the actual checkout's AGENTS.md, including "Conditional indexing-recovery
authorization (owner decision, October 6, 2026)". This is the active permission
policy for this task. Older prompts and reports describe historical restrictions;
do not rerun them as tasks or let their blanket GSC bans obscure the new conditional
exception. Production/staging, healthcare, credential and scope boundaries still apply.

The latest authoritative investigation is:

- reports/indexing-root-cause-20261006T135247Z/executive-summary.md

- reports/indexing-root-cause-20261006T135247Z/new-findings.md

- reports/indexing-root-cause-20261006T135247Z/root-cause-analysis.md

- reports/indexing-root-cause-20261006T135247Z/remediation-proposal.md

- reports/indexing-root-cause-20261006T135247Z/url-status-matrix.csv

- reports/indexing-root-cause-20261006T135247Z/hypothesis-ledger.csv

- reports/indexing-root-cause-20261006T135247Z/timeline.csv

- reports/indexing-root-cause-20261006T135247Z/evidence-index.md

- reports/indexing-root-cause-20261006T135247Z/validation.md

Its matching data/indexing-root-cause-20261006T135247Z/ contains full raw read-only
Inspection/sitemap API responses, real downloaded Page indexing/Crawl Stats CSV ZIPs,
selected UI field transcriptions, selected Google-retained HTML/header excerpts,
robots content and preservation/hash manifests. Verify paths exist; detailed private
evidence is ignored and might not accompany another clone.

Use earlier evidence selectively for a named question:

- data/reports indexing-root-cause-20261006T012643Z: real Google public live tests,
  rendered text comparison, current DNS-verified Google InspectionTool origin
  records, bounded WordPress page/menu/SEO metadata and retained revision history.

- data/reports indexing-root-cause-20261006T003538Z: 30 retained origin archives,
  verified selected Google IPs/requests, differential public delivery, actual
  sitemap/plugin/layout configuration observations and exact artifact proposals.

- data/reports indexing-investigation-20261005T235904Z: discovery/links, variant
  comparison, content comparison and parsed whole-sitemap baseline. Start with
  data/indexing-investigation-20261005T235904Z/sitemap-analysis.json and corresponding
  public-observations.json for sitemap entries and raw response provenance.

- data/20261005T220630Z and reports/20261005T220630Z: original GSC/crawl baseline.

- docs/audits/2026-10-05-public/ and docs/audits/2026-10-05-followup/: dated baseline.

Reports with older "owner sign-in required" statements are historical. The latest
account-access-resolution.json and completed account observations resolve that need.
The old next-account-read.md preserves the pre-login handoff under a resolved notice.
Do not ask the owner to log in again unless a fresh supported browser access attempt
shows the actual session is no longer usable.

Read README.md, docs/LOCAL_DEVELOPMENT.md and seo_agent/auth.py, gsc.py, crawl.py,
__main__.py as needed to reuse the established tooling; do not reinstall a working
environment or trigger a fresh full snapshot as your first step.

## Facts already established: reuse, do not re-investigate

1. Both desired URLs were unknown in the correct authenticated property UI and
   raw read-only API on October 6. Crawl/canonical fields are absent or N/A/
   UNSPECIFIED, not a reported noindex, fetch error or alternate canonical:
   - https://meadowandmindpsychology.com/individual-therapy/
   - https://meadowandmindpsychology.com/affordable-therapy-pennsylvania/
   Unknown is distinct from Discovered-currently-not-indexed and
   Crawled-currently-not-indexed.

2. Actual Google-received source links are proven, with exact saved excerpts:
   - FAQ last crawl 2026-08-04T05:22:12Z: five individual-therapy anchors, two
     affordable anchors, including a therapy body link.
   - Homepage last crawl 2026-10-04T08:42:39Z: six individual-therapy anchors,
     two affordable anchors, including navigation/card/text routes.
   Both saved responses are 200, index/follow and self canonical. Selected anchors
   have no nofollow. This eliminates the sampled "Google only saw old source pages
   without these links" explanation. It does not prove crawl-frontier retention.

3. Google's public Rich Results Test/InspectionTool successfully fetched and
   rendered the exact services on October 6:
   therapy 00:46:29Z; affordable 01:31:31Z; assessment control 01:32:24Z.
   All were 200, crawl/index allowed, with correct self canonicals and substantive
   service text matching anonymous mobile delivery. Affordable/control origin
   records independently corroborate the tool requests with verified Google IPs.
   These are user-triggered tests, not ordinary indexing crawls. Do not redo all
   three tests merely to rediscover healthy output. RRT is not a sitemap validator.

4. Thirty existing origin archives, September 5-October 5, were already obtained
   and parsed: 22,608 rows, 22,606 parsed; 210 selected verified-Google records.
   They include normal root/robots/control traffic, without selected routine
   exact-path therapy/affordable requests in that bounded coverage. Edge/log
   completeness is not established; absence does not prove Google never visited.
   The completed work did not find a responsible Google-blocking hosting rule.
   Do not ask for the same generic 90-day logs or enable/change diagnostic retention.

5. Bounded WordPress metadata/history was already acquired read-only:
   therapy page778, affordable1403, assessment716, home8, real FAQ585,
   active Entire Site header14 and footer346.
   Services are published, unprotected, with stored index metadata and no retained
   canonical override/old-slug row. Retained FAQ/home therapy links date to June1/2;
   revision/publication/lastmod labels are not independently proven public dates.
   No broad database export, clinical records or another revision export is needed.

6. The submitted sitemap index's Google record is stale:
   last submitted 2025-07-16T19:11:42.215Z;
   last downloaded 2025-12-09T12:07:40.774Z; UI Success; zero discovered pages.
   Google exposes only post-sitemap.xml and elementskit_template-sitemap.xml as
   children, both Couldn't fetch; API pending, missing submission/download times,
   zero errors/warnings. page-sitemap.xml is absent from that child view.
   Google's saved homepage nevertheless names page-sitemap.xml as a referring page
   and shows Temporary processing error for sitemap information.
   These reporting observations do not prove the page sitemap is currently
   unreadable, Google never received it, or Google has an internal bug.

7. The prior parsed public index contained FIVE children:
   post-sitemap.xml, page-sitemap.xml, elementskit_template-sitemap.xml,
   category-sitemap.xml and local-sitemap.xml.
   The page child contained the two services and assessment, plus legitimate
   home/FAQ/couples/rates/providers/blogs/contact and other service landings.
   This is dated baseline, not acceptance of today's entire generated sitemap.
   Some later .body files named after sitemaps contain a 403 HTML response.
   Read status/root/provenance before treating any saved body as actual XML.

8. Account Page indexing is dated September20,2026: 12 indexed/6 excluded.
   Examples are redirect paths /home-2/ and /comprehensive-evaluations/, literal
   /* and /wp-content/* redirect-error URLs, and literal search-term placeholders.
   They do not establish wildcard server rules excluding the therapy services.
   Displayed Crawled-currently-not-indexed count is zero. Assessment is indexed,
   last crawl 2026-10-02T09:21:53Z, self canonical; no referring sitemap reported.
   Missing referring-sitemap association alone does not establish indexing failure.

9. Crawl Stats July7-October3: 2,527 requests, 18,398,272 bytes, 89ms average;
   exact purpose ratios 99.68% refresh/0.32% discovery. Counts include resources.
   The discovery drilldown has 8 aggregate requests and separately 9 representative
   examples; examples are not exhaustive. Host reports no problems/acceptable
   robots/DNS/connectivity fail rates. Retained September4/6 robots allow services.
   Manual/security reports are clear and no removal requests appear in the exposed
   six-month views. None establishes crawl-budget starvation, a penalty, a need for
   paid hosting, or universally perfect historical transport.

10. Separate sitemap/artifact issues are mapped and require whole-sitemap review:
    - Rank Math Templates XML and HTML inclusion switches are on. Standalone
      header14/footer346 query URLs have effective HTTP noindex, conflicting HTML
      index meta, and active Entire Site assignments. Keep embedded layouts intact.
      Header14 standalone FAQPage has17 questions; this is separate schema hygiene.
    - Default category term1/psychology is a two-post grouping overlapping /blogs/;
      category sitemap inclusion is on. Its intended independent search role still
      requires an owner decision; do not silently delete or blanket-exclude taxonomy.
    - Rank Math Local Sitemap inclusion is on; KML has blank address/phone/geo,
      inconsistent observed primary/www MIME, known sitemap consumer and unknown
      external consumer role. Treat it as a resource, not an HTML service landing.
      Do not invent clinical/business facts or delete the resource/module.
    Exact proposals/current controls are in prior remediation-proposal.md files.
    Their cleanup has NOT been implemented and is NOT a demonstrated therapy cause.
    Some directive/schema/MIME emitters remain unmapped; do not invent PHP hooks.

The strongest existing conclusion is a missing reported ordinary crawl/index
record despite received links and successful current Google-tool access. The
mechanism remains unproved. Preserve uncertainty; don't relabel it a quality
rejection or a guaranteed sitemap cure.

## New work: complete these phases in order

### A. Identify what remains to be tested

Create a short evidence-reuse table identifying the completed fact/source and the
new question for each proposed test. Then proceed with the work. No need to ask the
owner to approve routine read-only diagnostics. A repeat must be justified by a
specific freshness need, changed condition, missing field or post-action comparison.

Use the existing .venv and same-project token for read-only API reads. OAuth remains
exactly https://www.googleapis.com/auth/webmasters.readonly. The authenticated
practice account previously had verified-owner access to the existing prefix
property; Google's wrong-account domain-verification screen is not a DNS requirement.
Account selectors/tab IDs may change: inspect current supported browser state,
verify exact property, and do not assume a historical tab handle is current.

### B. Review the WHOLE sitemap before any recovery request

Read the current robots declaration and index; follow all actually listed children
and nested indexes within the practice host, recording redirects rather than
silently extending to other hosts. Save raw bytes/status/headers/UTC/hashes.
Respect robots, pace requests, reuse valid existing samples, avoid broad or
performance-affecting crawls and never bypass a denial/security challenge.

Produce a complete entry inventory and explicit desired disposition for every
URL/resource: keep, omit, correct, or owner role decision needed, with evidence.
Include intended landing role, actual child/provider, HTTP/directives/canonical
evidence and provenance, index state where available, and reason for the decision.
Reuse dated evidence and label it; fresh-read gaps or denied clients are not facts
about Google's delivery. Use bounded reads for unmapped/currently changed entries.

Evaluate absolute preferred HTTPS host URLs, XML validity/namespace/escaping,
duplicates across children, redirected/noncanonical/404/noindex entries, missing
desired pages, truthful lastmod use and canonical consistency. Consider child
pagination, image/video extensions and KML/resource intent without treating resources
as ordinary HTML pages. Do not fabricate change dates or inflate sitemap priority.
XML sitemap noindex headers do not by themselves justify removal of those headers.

Present current versus recommended complete hierarchy/URL list, not just a child
or two target URLs. The owner must be able to judge whether we like the sitemap
as a whole. Explain layout/category/KML decisions in plain terms, preserve useful
services/posts and required embedded navigation, and flag factual/role confirmations.
No sitemap generator/settings change is authorized by this task.

### C. Test the remaining sitemap-fetch question with Google

Use the supported authenticated Search Console URL Inspection Test Live URL route
for the actual index/page child and relevant failed children when useful. Capture
crawl permission, actual fetch outcome, response/parse details and time where offered.
Google's official sitemap debugging guidance supports this route:
https://support.google.com/webmasters/answer/7451001

This is a new question: can Google's current fetch retrieve the actual XML sitemap
hierarchy? It is not answered by an old submitted record or a healthy service-page
test. A sitemap's lack of HTML indexing eligibility is not a sitemap-fetch failure.
Live Inspection transport success also does not prove routine sitemap ingestion.
If the UI doesn't offer usable XML details, preserve the limitation and use supported
read-only evidence; do not substitute a Rich Results score or spoofed user-agent.

If a real failed fetch is observed, compare its exact host/path/time/status/body
with a successful child/control and available retained provider data. Map the
responsible generator/cache/redirect/security setting only if evidence identifies
it. Prepare its exact current/proposed value, validation and rollback locally.
Do not disable security, purge caches, buy hosting or rewrite the services speculatively.

### D. Prepare the approval gate, then a bounded recovery if warranted

Read AGENTS.md's gate literally. Before any Submit or Request indexing:

- Present the complete sitemap review, desired manifest, unresolved issues and
  exact proposed one-time browser batch with the affected property/full URLs,
  current versus intended state, rationale and expected observations.

- Ask the owner to approve the specific whole-sitemap version and batch. Cite the
  owner's sitemap condition and AGENTS.md as the reason this approval is required.

- Continue independent read-only work while approval is pending. No approval is
  implied by silence, timeout, running this prompt or merely approving one child.

- If recommended sitemap changes are necessary, an approved local draft is not a
  served sitemap. Keep production/staging boundaries; do not submit the existing
  unacceptable sitemap or bypass review through direct page submission/indexing.

After actual approval, verify the served semantic URL/inclusion manifest and relevant
successful fetches match the review. Use only the smallest expressly approved subset:
submit/resubmit the current index once, directly submit page-sitemap.xml once if
justified, and/or request indexing once each for the two preferred therapy URLs.
No sitemap deletions, additional URL campaigns, Validate fix or broader OAuth.
Use browser UI for these approved writes; do not change API scopes or re-authenticate
to obtain write scopes.

Prefer an intervention sequence that preserves causal interpretation. Record any
combined batch as combined; an eventual success cannot identify which action helped.
Save before/after raw reads and exact UI acknowledgement. "Request accepted" is not
"indexed"; a live test is not a routine crawl. No request can guarantee indexing or
retroactively prove the original cause. Repeated requests do not accelerate crawling:
https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl

### E. Interpret new evidence and recommend the fix

- XML fetch/parse failure: recommend the narrow mapped transport/generation fix;
  distinguish old UI history from a reproduced present fault.

- Sitemap processing improves/new URLs recognized: document the exact changed
  state, with recovery inference and historical-cause uncertainty separately.

- Services become discovered but uncrawled: discovery is established; diagnose
  scheduling with actual observations without inventing a crawl-budget cause.

- Services gain a successful recorded crawl but remain excluded: investigate
  selection/duplication and rendered content for that actual phase.

- Different Google canonical: examine the actual alternate URL before proposing
  a correction; keep healthy intended canonicals unless a conflict is demonstrated.

- Services become indexed: confirm Google canonical and measure relevant non-branded
  query/page visibility. Indexing alone does not solve ADHD/Paoli ranking.

- Still unknown: state exactly which recovery acknowledgement/processing records
  are present or missing; update the existing evidence-backed Google-side case.
  No support/community/feedback message is authorized for transmission.

Finish useful work now; Google can take days to weeks. Give dated read-only follow-up
checks at about 7 and 14 days after an actual intervention and the observations that
would change the decision. Don't idle/poll indefinitely, create an automation, or
promise an indexing deadline. If no intervention is approved/performed, say so and
don't imply a recovery observation period has started.

## Deliverables and completion checks

Create new ignored data/indexing-recovery-<UTC>/ and reports/indexing-recovery-<UTC>/.
Preserve all earlier artifacts. Produce:

- executive-summary.md: genuinely new finding, cause/recovery confidence, next
  recommended action and what remains unproved; distinguish indexing from ranking.

- evidence-reuse.md: source-by-source reuse and reasons for any repeated tests.

- sitemap-review.md: whole current/proposed hierarchy, decisions, technical checks,
  unresolved roles and concise owner-review presentation.

- sitemap-current.csv and sitemap-proposed.csv: every child/entry/disposition,
  evidence references; hashes identifying actual XML and a semantic manifest.

- google-sitemap-fetch.md and raw read-only fetch/Inspection evidence where offered.

- recovery-plan.md: exact conditional batch, current/intended state, approval
  reference/status, acceptance checks, asynchronous/no-undo limits and next dates.

- action-log.md: truthful UTC/actions/results, or explicit "none performed".

- recommendations.md: mapped fix/proposed deltas, affected URLs/settings, evidence,
  impact/confidence/effort, clinical confirmations, validation and rollback.

- validation.md and evidence-index.md: raw hashes, evidence limitations, preservation,
  ignore checks, correct property/unchanged scopes and authorization compliance.

Do not put private account/log/database evidence into tracked prompts or Git. Exact
excerpt/transcription files are not full HTML/screenshot exports; label their scope.
Never print credentials or patient/form information. No new agents/chats/automations.

Before finishing, answer: What new fact distinguishes the competing explanations?
Have we reviewed the entire sitemap? Is the current generated sitemap acceptable,
or exactly what must change first? What approved action occurred and what did it
establish? What fix is justified, and what remains unproved? Do not treat pending
owner sitemap approval as a root cause or claim that a proposal fixed the site.
