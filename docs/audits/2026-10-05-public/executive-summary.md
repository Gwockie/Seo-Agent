# Meadow & Mind: read-only local SEO audit

Tracked public-only copy of the October 5 audit. Raw HTML/assets and future private Search Console exports remain ignored under data/ and reports/. This is a historical baseline, not current account data.

Prepared October 5, 2026 (America/New_York). Public evidence collected starting 16:41 EDT; folder timestamp is UTC. This is a **public audit, not a Search Console snapshot**.

## What the evidence supports

The public site already explains ADHD testing, psychological assessments and individual therapy, and repeatedly displays a Paoli address. It is not missing an ADHD offering in its content. The clearest on-site opportunity is to make the existing assessment landing page's ADHD intent more prominent in its title, heading and contextual links.

Actual underperformance, query rankings, impression volume, CTR and Google-selected landing pages cannot be quantified here. Neither `secrets/client_secret.json` nor `secrets/token.json` exists in this checkout. There are no historical snapshots or completed reports here; the earlier 06c2 checkout also had only a data placeholder and no reports. No credentials were printed or copied, consent was not initiated, and no property identifier was guessed.

### Why might visibility be insufficient?

**Observed on-page facts:** the homepage title targets Pennsylvania rather than Paoli. The assessment page title is “Psychological Assessments in Paoli | Meadow & Mind,” its primary H1 is “Comprehensive Psychological Assessments,” and ADHD is a later H2. The page has a second H1 containing its introductory sentence. Its useful four-stage assessment process and ADHD age-group content already provide a substantial foundation. Therapy's title and introduction already identify Paoli.

**Inference:** broad assessment positioning may understate ADHD relevance for the owner's priority searches. A more explicit service heading/title and clearer routes into the assessment page are reasonable improvements. Two H1s are a clarity/accessibility cleanup, not proof of a ranking penalty. Generic titles alone do not prove why the site ranks where it does.

**Unverified hypotheses:** Google Business Profile completeness, distance from searchers, citations, independent links, competition, qualified demand and mobile rendering may contribute. None has been measured well enough to assign a causal share.

### Does Google understand the ADHD assessment offering?

The crawlable content supplies clear ADHD testing information; the homepage mentions ADHD evaluations, the assessment page describes ADHD testing, FAQs explain assessments, and an ADHD article links to the service page. Google has material from which to understand the offering. Whether Google actually associates the desired queries with that page is **unknown without query/page performance and URL Inspection**. Search-engine retrieval surfaced the assessment page, but that is neither a local rank measurement nor current index verification.

### Are there indexing problems?

No confirmed P0 blocker was found on the homepage, assessment or individual therapy page. Each returned HTTP 200, a canonical matching its URL, an index/follow robots meta directive and no observed X-Robots-Tag noindex. Robots.txt allows their paths. The assessment and therapy URLs appear in the public page sitemap.

There is a smaller consistency issue: the sitemap lists two ElementsKit header/footer template URLs whose HTTP responses carry **X-Robots-Tag: noindex**, although their HTML meta tags say index. Their restrictive header means they should not be treated as indexable landing pages. This is sitemap hygiene, not proof that the service pages are blocked. The crawler also found `locations.kml`, an XML document incorrectly served as text/html; it is not a service page. Google's indexing verdict, chosen canonical, crawl history, manual actions and property-level coverage remain unavailable.

## Five highest-value opportunities

| Order | Opportunity | What is observed / what is uncertain |
|---|---|---|
| 1 | Clarify ADHD/local intent on the existing assessment URL | General assessment title/H1, strong existing ADHD content. Ranking impact needs GSC measurement. |
| 2 | Improve contextual routes and contact action | Home card says “Comprehensive Evaluations”; assessment learning link goes to /blogs/ instead of the named ADHD article; no assessment-specific body contact action observed. |
| 3 | Establish the query/page and indexing baseline | OAuth files and all GSC datasets absent. Read-only data would resolve actual landing-page alignment and cannibalization. |
| 4 | Verify practice identity across the site, schema and Business Profile | Visible address/phone exist; sampled Organization JSON-LD lacks address/phone. Preferred name, mailbox, clinician facts and profile not owner-confirmed. |
| 5 | Measure mobile rendering, then reduce demonstrated front-end cost | 32–44 linked stylesheets and 25–27 scripts across the three pages; large homepage image source. No usable mobile CWV or Lighthouse result. |

The first implementation proposal is **Batch A: eight specific edits across the existing assessment page and one homepage card**. Exact current/proposed text, affected elements, confirmations, tests and rollback are in [proposed-edits.md](proposed-edits.md). It preserves the assessment URL and its autism/psychoeducational content. No new ADHD URL or town pages are proposed.

## On-site versus off-site

On-site: page titles/headings, body contact routes, useful article links, contact-label consistency, factual entity markup, template-sitemap hygiene and measured asset scoping. The existing navigation and footer already provide widespread service links; this is not an orphan-page problem in the sampled graph.

Off-site: verify the real Business Profile and its categories, services, address, phone and website destination; inspect public citation consistency and actual local competitors before proposing changes. Local results involve relevance, distance and prominence. Website copy cannot eliminate distance constraints. See [Google's local ranking guidance](https://support.google.com/business/answer/7091). No profile edits, review requests or outreach occurred.

## Performance and hosting decision

Keep reported SiteGround StartUp and defer the $13/month upgrade. Public stylesheet evidence identifies Hello Elementor 3.4.4; loaded asset URLs identify Elementor and Elementor Pro code. Child-theme status, PHP, installed plugin versions, licensing, optimizer settings and server resources remain unverified.

Nine desktop-client GET samples returned headers in approximately 42–60 ms. Those samples use a reused session on this machine and may reflect its network/proxy/cache path; they do not measure PHP execution or mobile user experience. Pages exposed `Cache-Control: no-cache` and `X-Proxy-Cache: MISS`, but that does not establish the entire cache configuration. PageSpeed mobile API calls returned 429 quota errors on all three pages. Headless Edge failed to start, so no browser waterfall, screenshot, LCP, INP, CLS or Lighthouse score was produced. Do not infer an upgrade benefit. Details and a repeatable measurement plan are in [performance-evidence.md](performance-evidence.md).

## Information needed from the owner

1. Search Console Desktop OAuth client plus consent from an account with access, or dated query/page, page, query and indexing exports. Use only `https://www.googleapis.com/auth/webmasters.readonly`. Once configured, list properties and select the exact matching returned property before a fresh 90-day snapshot with read-only Inspection.
2. Confirm current ADHD assessment availability, ages accepted, in-person assessment location and whether the proposed positioning accurately represents the practice.
3. Confirm preferred public practice name, address/suite, telephone and contact mailbox; provide the real Business Profile URL.
4. Read-only WordPress/theme/plugin/version inventory and sanitized Elementor exports for the two affected pages; verify child theme and Pro status. No production editor access is needed for this proposal.
5. Existing dated mobile PSI/Lighthouse/CrUX evidence, if available; otherwise collect controlled mobile lab runs and field evidence when accessible.

Public facts are evidence, not clinician signoff. No code is drafted against imaginary theme functions or unconfirmed clinical facts. No production/staging writes, transfers, plugin installations, DNS changes, sitemap submissions or indexing requests were made.
