# Resolve the indexing contradictions: acquire the missing evidence

Work in `C:\Users\keyse\.codex\worktrees\6550\local-seo-agent` on `https://meadowandmindpsychology.com/`.

The owner wants an investigation that gets beyond another list of unknowns. Your job is to acquire new evidence, test the competing explanations, and identify what specifically prevents or has prevented Google from recognizing the desired service URLs. Prioritize `/individual-therapy/`, then `/affordable-therapy-pennsylvania/`. Close out the other audited unknown URLs according to their actual purpose.

Do the investigation, not just a plan. Do not stop at “don't know,” “Google decides,” “wait for indexing,” or another request for logs that you have made no effort to obtain. Repeating the existing HTTP/Inspection checks is not meaningful progress unless something changes or the new check answers a different question. Existing template/KML issues do not count as an explanation for therapy.

Persistence is mandatory; fabricated certainty is prohibited. Find facts that discriminate between explanations. If a necessary source is inaccessible, establish the exact access dependency through an actual attempt, request the smallest useful owner action immediately, and continue every independent investigation path. You cannot turn missing evidence into a claimed root cause.

## Read and reuse before collecting

- `AGENTS.md`, `README.md`, `docs/LOCAL_DEVELOPMENT.md`, and `prompts/indexing-investigation.md`.
- The preserved public baseline and follow-up under `docs/audits/2026-10-05-public/` and `docs/audits/2026-10-05-followup/`.
- If present in this actual checkout, `data/20261005T220630Z/` and `reports/20261005T220630Z/`.
- If present, `data/indexing-investigation-20261005T235904Z/` and `reports/indexing-investigation-20261005T235904Z/`, especially investigation, matrix, raw Inspection, discovery analysis, chronology, sitemap metadata, proposals and validation.
- `seo_agent/auth.py`, `gsc.py`, `crawl.py`, and `__main__.py`.

Private evidence is ignored and may not accompany a clone. Verify existence. Never invent absent exports. Preserve both prior investigations and the dated baseline; create new timestamped evidence/report folders.

The starting set is:

1. `https://meadowandmindpsychology.com/individual-therapy/`
2. `https://meadowandmindpsychology.com/affordable-therapy-pennsylvania/`
3. `https://meadowandmindpsychology.com/category/psychology/`
4. `https://meadowandmindpsychology.com/?elementskit_template=faqs`
5. `https://meadowandmindpsychology.com/?elementskit_template=home-2`
6. `https://meadowandmindpsychology.com/locations.kml`

Reconcile this with actual exports. The separate `/home-2/` path is a redirect control, not the footer query URL.

## Evidence you must move beyond

Both service URLs were publicly 200/indexable/self-canonical, in the page sitemap and one link from home. Each received links from twelve pages reported indexed. Therapy also had homepage and FAQ body links. Stored Inspection continued to return unknown with unavailable crawl/fetch/canonical fields. These facts already eliminate several simplistic current-public-output explanations.

The missing causal evidence concerns what Google actually fetched/discovered, when the URLs and discovery signals became available, and whether authenticated/live Google views disagree with stored results. Make those questions the center of your work. Do not prescribe adding an existing sitemap entry, removing XML sitemap noindex, increasing a word count, buying hosting, or changing an existing healthy canonical without evidence.

## Required investigation paths

### 1. Get Google's detailed account evidence, not just the CSV verdict

Reuse the existing `.venv` and same-project authorized token. Run `sites` first and select the matching property actually returned. Do not guess a domain property. OAuth must remain exactly `https://www.googleapis.com/auth/webmasters.readonly`; preserve conflicting files and never borrow tokens or print secrets.

Use read-only API calls for stored Inspection and submitted-sitemap metadata, preserving full raw responses and UTC retrieval times. The API does not provide a live fetch. Capture absent/UNSPECIFIED fields literally.

Actively check whether an existing authenticated Search Console browser session is available. Use the supported browser tools and select the exact practice property. Read the indexed-URL Inspection details, Discovery, Page indexing reports/examples/history, and sitemap detail/history. Obtain exact reported reasons, crawl dates, sitemap association, referring pages, last read, processing status and discovered counts where the UI supplies them. Inspect an indexed control through the same property and interface.

A read-only **Test Live URL** fetch is permitted for the two service URLs and one appropriate indexed control if the current UI/access supports it. Capture fetch availability, robots/index directives, rendered content, resource errors and returned HTML where offered. Keep the distinction between live availability and stored index status. Never click Request indexing, Validate fix, submit/delete sitemap, or property/configuration controls.

If the browser is not signed in, identify that immediately and request owner sign-in to the existing property. Do not spend the turn merely repeating API inspections. If live testing is unavailable, record the actual attempted route and continue the other paths.

### 2. Establish whether verified Googlebot reached these exact URLs

Look for existing, authorized, read-only hosting/access-log or Search Console crawl evidence. Prefer an already accessible read-only log viewer/download or owner-provided sanitized extract. Do not install logging/export plugins, enable diagnostics, modify retention, change security settings or create a log-producing website job.

Request only a targeted extract if access is missing: existing retained history for the two service URLs, their observed redirect variants, the declared sitemap index/page sitemap, and an indexed control. Ask for UTC timestamp, exact path/query, status, redirect location, response size and verified-bot classification; include response/challenge details only if already available. Ask for the provider's available date range, not an assumed 90-day retention period. Exclude patient/form data, credential contents and unrelated visitor records.

Distinguish a verified Google crawler from a spoofed Googlebot user-agent. A local request with a Googlebot string is only a differential client test. Use existing provider verification or official bot-verification methods when authorized evidence allows it; do not claim actual Google delivery from spoofing.

Answer separately: was there a request; did it reach the intended host/path; what did it receive; did redirects resolve; was content complete; did a sitemap request occur before/after the service's public availability? Compare failures with an indexed control. No requests in a log with incomplete coverage do not prove Google never visited.

If logs are inaccessible, name the exact provider/screen/export and required fields, and ask the owner for that narrow action while continuing. “Need logs” without an attempted access path is insufficient.

### 3. Reconstruct the real URL and discovery chronology

Use source-declared public WordPress REST links or verified page mappings to read public page records where available. Obtain ID, slug, status, link, publication/modification labels and relevant public content; avoid users, submissions, private records and broad database exports. Inspect actual public HTML/JSON-LD, sitemap modification labels, existing local evidence and available dated public archives. Do not treat plugin date labels as proof the URL was publicly accessible then.

Seek dated proof of first public availability, previous slug, prior redirects/noindex/password protection, and when the indexed homepage/navigation/FAQ links began pointing to these exact URLs. Ask for narrow sanitized history/export evidence where public records cannot establish it. Do not open an autosaving page/template editor or restore a revision.

Build a timeline separating publication labels, independently observed public availability, discovery-link observations, sitemap inclusion, actual Googlebot activity and stored Inspection retrievals. A plausible age story without dated evidence is not a diagnosis.

### 4. Test delivery differences with controlled comparisons

For each primary service and an indexed control, collect anonymous, robots-respecting source and rendered content. Test only meaningful bounded differences: preferred URL versus known redirect variants; normal desktop versus mobile client; ordinary cache response versus a documented read-only fresh-response method if supported. Record cookies/authentication state, user-agent, headers, status/hops, canonical/directives, body hash and UTC time. Do not change cache settings or purge caches.

Inspect whether any response becomes an error/challenge, empty shell, wrong page, redirect loop, noindex or conflicting canonical. Compare the live Google test if obtained. Check service text visibility and relevant resource failures, not just a screenshot. Authenticated browser rendering cannot substitute for anonymous delivery.

Do not bypass a WAF/security challenge, use evasion proxies, disable protections, brute-force variants or submit forms. Two or three bounded comparable samples can distinguish a suspected intermittent fault; endless repeats do not.

### 5. Close out every artifact using actual integration evidence

For the category, compare its purpose/listing with `/blogs/`, current links and intended index policy. For template query URLs, verify header/footer identity, HTTP noindex, sitemap inclusion, template assignments and the source of any misplaced FAQ schema. For KML, verify its generator, consumers, actual XML fields, primary/www MIME and discovery policy.

Use existing local source, sanitized exports or safe read-only inventories/configuration views where authorized. Never load an autosaving editor. Identify the actual setting/filter/template responsible when evidence permits; do not fabricate PHP hooks or stored option values. Intentional exclusion is a valid resolution for a non-target artifact, but cannot close a desired service-page contradiction.

### 6. Test and rank explanations explicitly

Maintain a hypothesis ledger per URL. Include the predicted observation, actual test/source, result, confidence, contrary evidence and next discriminating test. Prioritize:

- Exact URL never entered Google's reported discovery despite currently available routes.
- Routes or indexability changed after historical source/sitemap processing.
- Verified Googlebot/CDN/WAF delivery differed from ordinary anonymous delivery.
- Intermittent status/redirect/content failure.
- A different canonical/variant held the historical Google record.
- Stored reporting and successful live/log evidence disagree.
- Content selection/duplication, only where Google's state or actual evidence supports that phase.
- Deliberate non-index policy for layout/archive/resource artifacts.

Unknown is distinct from Discovered-currently-not-indexed and Crawled-currently-not-indexed. Do not relabel it as quality rejection. No penalty, sandbox, crawl-budget starvation, plugin-score cause or hosting cause without evidence. Missing performance rows are not zero demand.

## Required result and stopping criteria

Create ignored `data/indexing-root-cause-<UTC timestamp>/` and matching `reports/` folder containing:

- `executive-summary.md`: lead with what NEW evidence establishes for therapy and affordable therapy, and what action that changes.
- `new-findings.md`: delta from the previous investigation; mark copied baseline facts separately. A repeated stored Inspection result or unrelated artifact issue is not a new service-causal finding.
- `url-status-matrix.csv`: every exact URL, desired index policy, old/current/live status, log/timeline findings, disposition and evidence references.
- `timeline.csv` and `hypothesis-ledger.csv`.
- `root-cause-analysis.md`: tested causal chain, contradictory evidence and confidence for each URL.
- `remediation-proposal.md`: actual affected setting/source/URL, exact observed current value, proposed delta, reason, factual confirmations, validation and rollback. If the actual integration is missing, state the precise output contract and the specific mapping needed; do not pretend speculative code is deployable.
- `evidence-index.md` and `validation.md`, with raw evidence hashes and preservation checks.

For each primary service, aim to reach a demonstrated cause or a narrowly supported explanation backed by new discriminating evidence. If the necessary source remains inaccessible after real attempts, deliver the concrete acquisition dependency, exact requested owner operation/fields, already completed tests and a decision tree whose branches specify what the missing result would establish. Label it as an access-dependent investigation rather than a root-cause diagnosis. Do not manufacture a finding to satisfy the wording of this task.

Before finishing, audit yourself: What NEW fact about therapy did I establish? Which hypothesis did it eliminate or strengthen? Did I actually pursue UI/live-fetch/log/history evidence? Am I hiding behind a generic unknown, or making a claim the evidence does not support? Have I provided the next executable step instead of a vague checklist?

“HTTP 200, unknown, ask for logs” is not an acceptable final deliverable. An evidence-backed explanation, a verified intentional exclusion, or a demonstrated access dependency with a completed discriminating investigation is required. Clearly separate facts, inference and untested possibilities; never assert certainty that the sources cannot support.

## Boundaries

This prompt authorizes investigation and local artifacts only. Preserve AGENTS.md's production prohibition and exact-approval requirement for any future staging write. No WordPress/Elementor edits/autosaves, publishing, imports, redirects/canonical changes, deletion, plugin operations, cache purges, DNS/hosting changes, sitemap submissions/deletions or indexing requests. No credentials, patients, fabricated clinical claims, broad scope grants or mass location pages. Do not dispatch another agent/chat or create an automation. Keep private detailed evidence ignored; do not overwrite prior reports or add private exports to Git.

Persist with useful, authorized read-only investigation until the strongest supported result and concrete next action are documented. Unavailable internal Google reasoning does not excuse shallow investigation, and persistence does not authorize invention or external writes.
