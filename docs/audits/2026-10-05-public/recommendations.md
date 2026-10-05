# Prioritized recommendations

Tracked public-only copy of the October 5 audit. Raw HTML/assets and future private Search Console exports remain ignored under data/ and reports/. This is a historical baseline, not current account data.

October 5, 2026. Public audit only. Evidence: [index](evidence-index.md), [query map](query-page-map.csv), and [performance record](performance-evidence.md). Scores: impact 1–5 = expected usefulness, confidence 1–5 = support for the diagnosis/recommendation, effort 1–5 = implementation complexity. Scores are judgments, not predicted traffic lifts. Clinical copy stays conditional until owner confirmation.

## P0 — investigate actual technical blockers; none confirmed

### R1. Obtain the read-only search/index baseline
- **Evidence:** OAuth client/token absent; no GSC query/page, queries, pages, opportunities or URL Inspection exports exist. Public 200/index directives do not establish Google's index state.
- **Page/query:** all ten target queries; homepage, assessment and therapy URLs.
- **Impact / confidence / effort:** 5 / 5 / 2.
- **Suggested action:** owner configures Desktop OAuth and consent at the unchanged readonly scope. Then run `python -m seo_agent sites`, choose the exact appropriate returned property (prefer an appropriate verified domain property if actually returned; otherwise the matching HTTPS URL-prefix property), and collect `snapshot --site "EXACT_RETURNED_PROPERTY" --url "https://meadowandmindpsychology.com/" --days 90 --inspect` using this existing .venv. Do not run auth blindly, copy credentials from another checkout, or request indexing. Examine all required GSC CSVs, compare chosen canonicals and record any inspection errors.
- **Measurement:** complete dated 90-day query/page baseline, target clusters, total page clicks versus query-attributed clicks, country/device segmentation, impressions, CTR, impression-weighted position and URL Inspection verdicts. Treat missing/anonymized/capped query rows as incomplete evidence.
- **Priority qualification:** this is a diagnostic prerequisite, not a confirmed outage. Promote an actual blocked/wrong-canonical service page to P0 only if inspection establishes it.

## P1 — priority service and local relevance

### R2. Give the existing assessment page an explicit ADHD/local lead
- **Evidence:** assessment title/H1 emphasize broad psychological assessment; later H2 says ADHD Testing; content covers children, teens and adults, plus four process stages. There are two H1s, including an introduction. See assessment HTML/text in the evidence folder.
- **Page/query:** /psychological-assessments-paoli/; all six ADHD queries and psychological testing Paoli.
- **Impact / confidence / effort:** 5 / 4 / 2.
- **Suggested change:** Batch A1–A5 in proposed-edits: ADHD/local title, revised description, broad-but-ADHD-explicit H1, intro converted to paragraph, local ADHD subsection heading. Preserve autism and psychoeducational material and current URL. No dedicated ADHD URL yet.
- **Confirmation:** ADHD service availability, age groups and assessment location.
- **Measurement:** relevant non-branded cluster impressions/clicks, intended landing-page share, position and CTR before/after an independently managed release; compare broader autism/assessment queries to detect a tradeoff. Content drafts/staging alone cannot change production rankings.

### R3. Make the practice/location identity useful and accurate
- **Evidence:** visible 30 S. Valley Road, Suite 307 / #307, Paoli PA 19301 and (484) 925-1546; homepage title is statewide. Sampled JSON-LD has Organization #organization without address/telephone. The local KML has empty address/phone/coordinate fields. Footer displays a spaced email while href points to rachael@..., not the displayed info@... mailbox.
- **Page/query:** homepage, shared contact display, contact page; Paoli and near-me searches.
- **Impact / confidence / effort:** 4 / 4 / 3.
- **Suggested change:** after signoff, normalize the chosen display name/address/phone/mailbox and add a concise factual Paoli service/location paragraph where useful. Review the existing Rank Math entity integration to enrich the same #organization entity rather than append a competing business. Consider a truthful healthcare business subtype only after confirmation; never infer Physician status. Omit unknown hours, coordinates, affiliations, reviews and ratings.
- **Confirmation:** preferred public name, real public practice location, primary telephone, mailbox, hours if supplied, eligible services. Exact plugin configuration and graph integration remain uninspected.
- **Measurement:** one consistent rendered graph, visible-content agreement, strict JSON plus semantic validation, applicable Rich Results Test in code mode, correct internal entity references and profile/site NAP consistency. Do not measure success with a plugin score or promise rich results.

### R4. Verify the actual Google Business Profile and local context
- **Evidence:** no profile URL/export, map-pack evidence, citations, competitor or backlink dataset supplied. Public content has a local address; off-site visibility is unknown. Google describes relevance, distance and prominence as local factors.
- **Page/query:** near-me and Paoli service searches; homepage/contact and profile website link.
- **Impact / confidence / effort:** 5 / 3 / 3.
- **Suggested action:** read-only review of the owner's verified profile, categories/services, public NAP, website URL, hours and duplicate listings; record query/location/date/device for a small relevant local competitor comparison. Review citations/links before recommending corrections. No profile mutations or contacting others.
- **Confirmation:** real listing, exact business identity and service facts.
- **Measurement:** dated location-aware observations, any authorized profile performance evidence, correct landing routes and qualified organic inquiries. GSC web results do not represent the complete map-pack funnel. Distance remains a constraint.
- **Source:** [Google Business Profile guidance](https://support.google.com/business/answer/7091).

## P2 — internal links, content structure, contact paths and performance

### R5. Strengthen the existing contextual assessment routes
- **Evidence:** assessment has 17 distinct inbound pages in this sampled graph, largely repeated navigation/footer links. Homepage body card anchor says Comprehensive Evaluations. Assessment's ADHD learning anchor goes to /blogs/. ADHD article's body link back says Click here to learn more.
- **Page/query:** homepage, assessment, ADHD article; assessment/testing intent.
- **Impact / confidence / effort:** 4 / 5 / 1.
- **Suggested change:** Batch A7–A8: name the homepage card clearly and point the assessment's learning link directly to the existing ADHD article with descriptive text. In a later separately reviewed edit, make the article's service link descriptive. Navigation is already connected; do not blanket-rename shared menus.
- **Measurement:** correct contextual href/label in HTML, keyboard/mobile usability, page alignment in GSC and existing analytics link evidence if available. Sample inbound counts are not a whole-site authority score.

### R6. Add a service-specific body contact action
- **Evidence:** the assessment and therapy pages contain global Contact links but no observed service-specific contact action in their main copy; homepage has Schedule A Visit.
- **Page/query:** /psychological-assessments-paoli/ first; /individual-therapy/ later.
- **Impact / confidence / effort:** 4 / 4 / 1.
- **Suggested change:** Batch A6 adds Ask about an ADHD assessment linking to the existing contact URL. Later therapy action: Ask about individual therapy, same verified route. Avoid promises about availability, turnaround, outcomes or insurance.
- **Confirmation:** owner approves that inquiry route and current service availability.
- **Measurement:** destination 200, clear focus/accessible name, mobile usability and existing consented conversion evidence. Any new analytics instrumentation is a separately reviewed change. Count qualified inquiries in aggregate, excluding PHI from this repository.

### R7. Complete mobile diagnosis before performance code
- **Evidence:** homepage 44 stylesheet/27 script tags, assessment 34/25, therapy 32/25; all these stylesheet links are in head. Elementor/Pro, ElementsKit, Ultimate Blocks, Sliderberg, Contact Form 7 and Site Kit assets appear. CF7 resources load on all three despite no form tags there. One lazy homepage source PNG is 1,562,804 bytes. PSI returned quota errors; browser launch failed. No field CWV or controlled lab results.
- **Page/query:** all three high-value pages.
- **Impact / confidence / effort:** 4 / 4 / 3. Confidence in any particular untested optimization is only 2/5.
- **Suggested action:** follow performance-evidence.md protocol. Investigate actual loaded font weights/subsets, responsive image transfer, render-blocking CSS and unused widget/form scope. Inspect enqueue registration, inline configuration, dependencies and optimizer settings before any dequeue/delay patch. Preserve jQuery, menus, form/booking and consent behavior.
- **Measurement:** repeated comparable mobile lab medians, waterfall and bytes/requests; field mobile LCP/INP/CLS at p75 where available; synthetic local functional checks. TBT is not field INP. No host upgrade recommendation without repeated server/resource evidence.
- **Source:** [Google's Web Vitals guidance](https://web.dev/articles/vitals).

### R8. Clean template discovery and schema scope
- **Evidence:** elementskit_template-sitemap.xml lists the header/footer query URLs; both have HTTP noindex. Header HTML schema contains a WebPage/FAQPage entity with 17 Q&A entries, while extracted visible header text contains contact/navigation only. Main service pages emit Article schema; there is no LocalBusiness or Service in the sampled graph.
- **Page/query:** two template URLs, FAQ page and service schema; indirect technical hygiene.
- **Impact / confidence / effort:** 2 / 5 for observed mismatch; 3 for selecting the exact remedy / 2.
- **Suggested change:** inspect actual template/post-type and Rank Math configuration read-only. Future separately approved staging batch should remove template-only entries from generated sitemap output while preserving their noindex and their use as layout components, and scope FAQ markup to pages with visible Q&A. Do not delete templates, block shared assets, submit/delete GSC sitemaps or change service indexing. Audit Article classification for service pages without assuming it causes a penalty.
- **Measurement:** regenerated output contains desired indexable URLs only; header/footer still render; correct noindex remains; structured data matches visible content. No production action by this agent.

### R9. Improve therapy clarity and resolve eligibility inconsistency
- **Evidence:** therapy title already identifies Paoli and introduction says adults; FAQ says individual therapy for adolescents and adults. H1 is Individual Therapy. Assessment DOM text alternates autism and psychoeducational content; mobile visual order has not been verified.
- **Page/query:** /individual-therapy/ and FAQs; therapy/therapist searches.
- **Impact / confidence / effort:** 3 / 4 / 2.
- **Suggested change:** after age eligibility confirmation, revise therapy H1 to Individual Therapy in Paoli and description to include in-person location only if confirmed; keep therapy as a distinct service destination. Resolve cross-page age wording. Inspect assessment mobile DOM/layout before changing section order.
- **Measurement:** truthful consistent eligibility, understandable heading sequence/mobile reading order, therapy landing-page share and qualified clicks. These are later changes, outside Batch A.

## P3 — longer-term authority and evidence-led expansion

### R10. Develop useful specialist content and prominence from measured gaps
- **Evidence:** existing ADHD article and mixed assessment page; no proven keyword cannibalization or competition/authority deficit.
- **Page/query:** informational ADHD article versus transactional assessment; therapy versus couples/affordable services.
- **Impact / confidence / effort:** 3 / 2 / 4.
- **Suggested change:** use GSC and owner-approved service expertise to choose a small number of useful questions/process explanations. Review strong local competitors and real affiliations/citations. Consider a dedicated ADHD landing page only if query/page evidence and enough clinician-confirmed distinct content justify it; map links/canonicals deliberately and review separately. Never create mass town pages or invent qualifications, testimonials or instruments.
- **Measurement:** non-branded growth by intent, relevant referral/organic inquiries and sustained query-page alignment across comparable periods. Outreach or external messages require explicit instruction.

## Measurement schedule

Collect the baseline before an independently arranged production release where practical. With final GSC data, compare equal 28-day windows after sufficient recrawl/observation time, then review 8–12 weeks and the comparable prior-year period if available. Segment by page, country and device; retain absolute clicks/impressions alongside CTR and impression-weighted position. Watch changes in query mix/seasonality. Compare clusters of actual queries with the target mapping, without treating anonymized/missing rows as zero demand.

For cannibalization, identify repeated transactional queries appearing on multiple pages and calculate their page impression/click shares over time. Occasional overlap is not proof of harm. Google URL Inspection is read-only; neither this plan nor the official sources authorize sitemap submissions or indexing requests.
