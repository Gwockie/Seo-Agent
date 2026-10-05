# Evidence index and limitations

Tracked public-only copy of the October 5 audit. Raw HTML/assets and future private Search Console exports remain ignored under data/ and reports/. This is a historical baseline, not current account data.

Audit date: October 5, 2026, America/New_York. Folder: public-audit-20261005T204139Z (UTC start 20:41:39 = 16:41:39 EDT). Repository: local-seo-agent (owner-selected checkout).

## Local/tool inspection

Read AGENTS.md, README.md, LOCAL_SEO_ROADMAP.md, docs/LOCAL_DEVELOPMENT.md, schema/performance/templates/staging-review task prompts and their src/deploy guidance. Used existing .venv (Python 3.13.5; requests, BeautifulSoup, pandas imported). No installs were required.

No previous audit reports/snapshots found in the requested checkout; data held only .gitkeep. secrets contains its README only: client_secret.json and token.json absent. Only existence was checked, never private content. The earlier chat checkout 06c2 had no useful historical reports either. Tool auth source fixes the sole scope at https://www.googleapis.com/auth/webmasters.readonly and rejects tokens with other scopes. No auth, property-list or snapshot command was run because configured authorized access was absent; no GSC files or empty synthetic results were created.

Public crawl used the unchanged seo_agent.crawl implementation with a 60-page cap, respecting robots and host boundaries. It discovered 18 rows: 15 normal HTML pages including one category archive, two template query URLs, and one KML resource. All returned 200. The KML is served with text/html but contains XML, so “18 HTML pages” would be misleading. Sample inbound counts reflect distinct crawled source pages, not unique links or a full web graph.

Initial page-save processing encountered a Windows-invalid filename for query URLs; the existing crawl was retained and page extraction was rerun with safe template filenames. A later UTF-8 re-fetch decoded public HTML correctly. No audit tooling source was altered.

The checkout's Git metadata points outside the sandbox; initial ordinary git status failed and explicit-work-tree commands encountered permission errors. A final read-only check with an explicit work-tree succeeded under authorized local access: git check-ignore confirmed both reports/.../executive-summary.md and data/.../pages.json are ignored. Git status showed existing scaffold changes; this audit did not modify source, configuration or deployment files. No commit/push was attempted.

## Evidence files

Raw evidence is local-only under repository-relative data/public-audit-20261005T204139Z/; it is not included in Git. Files below refer to that folder:
- manifest.json: public-only identity, collection UTC time and access gap.
- crawl.csv: titles/descriptions/H1–H6, canonicals, HTTP/meta robots, JSON-LD types and sampled internal links.
- pages.json: final URLs, selected HTTP headers, link text/href, complete parsed JSON-LD and declared assets.
- home.html/.txt, psychological-assessments-paoli.html/.txt, individual-therapy.html/.txt: principal page source/text; other public pages and template outputs also saved.
- robots.txt and sitemap_index.xml, page-sitemap.xml, post-sitemap.xml, category-sitemap.xml, elementskit_template-sitemap.xml: live discovery evidence. These were fetched, not submitted or changed.
- locations.kml: public XML location artifact with empty address/phone/link/coordinate fields.
- wp-content__themes__hello-elementor__style.css: public theme header identifies Hello Elementor 3.4.4.
- asset-measurements.json and assets/: 85 downloaded first-party assets plus one externally referenced Google tag recorded without download.
- asset-inventory.csv: readable declaration/source inventory with page scope and dependency gaps.
- http-timings.json: nine local-client, unthrottled HTML samples.
- psi-attempts.json: mobile API 429 quota failures.
- evidence-hashes.json: SHA-256 for saved evidence at report completion.

The normal pages include home, assessment, individual/couples/affordable therapy, providers, rates, contact, FAQs, pre-adoption, letters, blogs, two articles and the psychology archive. No admin/editor, database, form submissions or patient data were accessed.

## Observations, hypotheses and gaps

| Topic | Observed | Hypothesis / gap |
|---|---|---|
| ADHD offering | Homepage ADHD evaluations; detailed assessment ADHD Testing section; supporting article/FAQs | Actual query/page alignment and demand unknown |
| Assessment structure | Broad title/H1; intro is second H1; local introduction; 17 sampled inbound pages | More explicit lead may help; no proven penalty |
| Therapy | Local title/intro; adult intro versus adolescent/adult FAQ | Confirm eligibility; no reason to merge with assessment |
| Canonicals/index directives | Principal pages 200, matching canonicals, index meta; no observed noindex | Google-selected canonical/indexing unavailable |
| Template discovery | Two query templates in sitemap, both HTTP noindex despite index meta | Hygiene correction requires config inspection, not deletion |
| Schema | Rank Math Organization/WebSite/WebPage/Article/Person graph; no sampled LocalBusiness/Service; Organization missing NAP | Exact plugin settings, truthful entity type and owner facts unconfirmed |
| FAQ template | Header template has WebPage/FAQPage with 17 Q&A while visible extracted output has navigation/contact | Check schema scope; template already HTTP noindex |
| Performance | Declared assets, source bytes, desktop HTTP timings | No mobile browser/field/lab verdict, no complete dependency graph |
| Hosting | Owner reports StartUp; nginx/MISS/no-cache observed | Actual tier, resource constraints and upgrade benefit unverified |
| Off-site | Public social links; address/phone visible | Real GBP, categories, reviews/citations/competition not audited |

Site public content is an evidence source, not certification of clinical accuracy. Do not infer qualifications, licensing, insurance, instruments or results. No ranking, impressions, CTR, Google index count, competitor strength or speed uplift is fabricated.

## Primary public references consulted

- [Practice homepage](https://meadowandmindpsychology.com/)
- [Assessment page](https://meadowandmindpsychology.com/psychological-assessments-paoli/)
- [Individual therapy](https://meadowandmindpsychology.com/individual-therapy/)
- [ADHD article](https://meadowandmindpsychology.com/beyond-the-screener-getting-an-accurate-adhd-diagnosis/)
- [FAQs](https://meadowandmindpsychology.com/faqs/)
- [Contact](https://meadowandmindpsychology.com/contact-us/)
- [Google title-link guidance](https://developers.google.com/search/docs/appearance/title-link): descriptive titles help communicate page content; Google may rewrite title links.
- [Google LocalBusiness guidance](https://developers.google.com/search/docs/appearance/structured-data/local-business): choose a truthful specific business type and validate visible-content consistency. No eligibility/rank guarantee. Official submission/recrawl suggestions are not authorized here.
- [Google local-ranking guidance](https://support.google.com/business/answer/7091): relevance/distance/prominence provide context, not a site-specific diagnosis.
- [Google Web Vitals](https://web.dev/articles/vitals): distinguishes field and lab evidence.

The web retrieval service could not open some service URLs directly; those pages were successfully fetched with owner-authorized public HTTP GETs and saved locally. Search result retrieval is not a reproducible Paoli or near-me rank check.

## Safety and final review

Only public read-only requests and local evidence/report writes occurred. No account scopes were changed, no auth consent was initiated and no staging/production systems were mutated. Source/deploy scaffold, disabled transfer placeholder and existing audit code remain intact. No staging target was invented. Proposed fragments originate in ignored reports and are reproduced in this public-only documentation; no executable source files were created because integration source and clinician confirmations are missing.
