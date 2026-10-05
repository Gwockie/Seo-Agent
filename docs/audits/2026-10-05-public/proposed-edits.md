# Local implementation proposal — Batch A

Tracked public-only copy of the October 5 audit. Raw HTML/assets and future private Search Console exports remain ignored under data/ and reports/. This is a historical baseline, not current account data.

October 5, 2026. **Status: local proposal only; clinician signoff pending; no website actions approved or executed.** Public HTML is the current-text evidence, not an Elementor export. Production writes are prohibited. There is no verified staging target.

## Selected first batch

Eight enumerated changes: seven on the existing assessment page and one homepage body-card label. Strengthen ADHD/local relevance and make the inquiry path clearer without creating a competing URL. Maintain the existing assessment slug and its autism, psychoeducational and process content. Therapy improvements, business schema, sitemap settings, shared navigation/contact fixes, optimizer settings and code are outside this batch.

Affected production URLs below identify source content only:
- Assessment: https://meadowandmindpsychology.com/psychological-assessments-paoli/
- Homepage: https://meadowandmindpsychology.com/

No staging URLs are assumed. Any future write review must map these elements to actual, verified staging URLs and current Elementor widget/metadata fields, recheck their values and include explicit approval of each action.

## Exact current and proposed values

### A1 — assessment HTML title
**Current:** Psychological Assessments in Paoli | Meadow & Mind

**Proposed:** ADHD Assessment in Paoli | Meadow & Mind Psychology
**Intended future action:** update only this page's title metadata in its verified existing SEO integration.
**Rationale:** bring the priority transactional ADHD intent into the title while retaining locality/brand. Preserve visible autism/psychoeducational material; monitor those query groups for tradeoffs.
**Confirmation:** ADHD assessment remains an offered service and appropriate lead intent.
**Rollback:** restore the exact current title from the staging pre-edit record.

### A2 — assessment meta description
**Current:** In-depth psychological assessments for ADHD, autism, and learning differences. Clear answers and thoughtful recommendations for all ages.
**Proposed:** Explore ADHD testing and psychological assessments in Paoli for children, teens and adults. Learn about the process and contact Meadow & Mind with questions.
**Intended future action:** replace only this page's description.
**Rationale:** identify service, locality and inquiry route without outcome promises. Existing page describes these age groups; this is still conditional on clinician confirmation.
**Confirmation:** accepted ages, availability and assessment location. Do not imply all ages if the owner has narrower eligibility.
**Rollback:** restore current description.
**Limit:** Google can choose a different snippet; no CTR lift is promised.

### A3 — assessment primary H1
**Current:** Comprehensive Psychological Assessments

**Proposed:** ADHD Assessment & Psychological Testing in Paoli
**Intended future action:** replace text in the current main-heading widget, preserving its H1 role.
**Rationale:** make the local ADHD intent clear while keeping broader psychological testing in view.
**Confirmation:** same service/location confirmations as A1/A2; no new instruments, credentials or diagnostic guarantees.
**Rollback:** restore original text in that widget.

### A4 — introductory sentence semantic role
**Current:** a second H1, with italic/nested spans and extensive pasted inline styling, reading: “Meadow & Mind Psychological Services provides comprehensive psychological assessments in Paoli for children, adolescents, and adults.”
**Proposed:** the same sentence in a paragraph below the single main H1:
```html
<p>Meadow &amp; Mind Psychological Services provides comprehensive psychological assessments in Paoli for children, adolescents, and adults.</p>
```
**Intended future action:** change only the intro element's role to a paragraph and remove pasted inline formatting from that sentence; reproduce appropriate spacing/typography through existing verified widget controls.
**Rationale:** make the heading hierarchy and introduction clearer. Multiple H1s are not diagnosed as an SEO penalty.
**Confirmation:** this existing age/location statement remains accurate.
**Rollback:** restore the original widget export, including original tag/formatting. Raw current markup is saved in assessment HTML.
**Implementation limit:** this fragment expresses desired output; it is not an importable Elementor template. Do not paste it into an external editor now.

### A5 — ADHD subsection H2
**Current:** ADHD Testing (preceded by invisible zero-width characters in the HTML).
**Proposed:** ADHD Assessment and Testing in Paoli
**Intended future action:** replace that H2 text, removing the stray invisible characters.
**Rationale:** give visitors a specific local service subsection; preserve its existing explanatory paragraphs and age-group bullets.
**Confirmation:** ADHD assessment/testing terminology and location are accurate.
**Rollback:** restore prior heading/widget text from the backup.

### A6 — add an assessment inquiry action
**Current:** no service-specific body contact action observed after the ADHD age-group list. Contact links exist in shared navigation/footer.
**Proposed insertion:** immediately after that list and before the learning-resource link:
```html
<p><a href="https://meadowandmindpsychology.com/contact-us/">Ask about an ADHD assessment</a></p>
```
**Intended future action:** add exactly one descriptive contact link through a suitable verified existing widget. No form, booking embed or analytics is added.
**Rationale:** provide a useful next step at the service explanation.
**Confirmation:** current service availability and that the existing Contact route is the intended inquiry route.
**Validation:** accessible link text/focus, no layout overflow, correct staging contact destination. The production URL in this draft identifies the observed route; a future local/staging implementation must use its corresponding local/staging path and prevent production form/booking/email calls.
**Rollback:** remove only this added element using its backed-up position/widget record.

### A7 — make the ADHD learning link direct and descriptive
**Current:** an H2 link reading “Click here to learn about getting an accurate ADHD diagnosis”; href is https://meadowandmindpsychology.com/blogs/
**Proposed:** a paragraph link:
```html
<p><a href="https://meadowandmindpsychology.com/beyond-the-screener-getting-an-accurate-adhd-diagnosis/">Read: Beyond the Screener — Getting an Accurate ADHD Diagnosis</a></p>
```
**Intended future action:** change this one element from H2 to paragraph, replace its text and href with the direct existing article route.
**Rationale:** avoid sending the reader to a generic archive and avoid treating a link instruction as a major service heading.
**Confirmation:** owner wants to retain/promote this existing article and confirms its clinical accuracy. Public publication alone is not a clinical endorsement.
**Validation:** destination 200, no redirects to unrelated content, accessible label and corresponding local/staging route.
**Rollback:** restore original H2, text and /blogs/ href.

### A8 — homepage assessment card label
**Current:** Comprehensive Evaluations; href is https://meadowandmindpsychology.com/psychological-assessments-paoli/
**Proposed label:** ADHD & Psychological Assessments
**Intended future action:** change only the text of this homepage body-card link; preserve its href and H3 role. Do not alter shared menus, the homepage hero, other cards or metadata.
**Rationale:** give the existing service route a clear ADHD cue.
**Confirmation:** this reflects the assessment offering without excluding its other services.
**Rollback:** restore Comprehensive Evaluations in this one widget.

## Local content/template outline

This is an Elementor-aware editorial plan, not invented PHP or template JSON:
1. One main service H1 (A3).
2. Factual introductory paragraph (A4).
3. Existing four-stage process, retaining current content.
4. ADHD H2 (A5), existing explanation/age bullets, one inquiry link (A6) and direct educational link (A7).
5. Existing autism and psychoeducational sections. Their HTML/text order is interleaved; inspect mobile layout/accessibility before considering a separate section-order change.
6. Existing shared contact/footer.

The public markup shows Elementor widgets, ElementsKit layout components and Elementor Pro assets. It does not expose complete widget configuration, template assignment or PHP enqueue hooks. **No deployable code, Elementor import JSON, schema loader or optimization patch was added under src/**: actual integration source and clinical facts have not been confirmed. Editorial fragments above remain safely in ignored reports. Sanitized read-only page exports can support a later exact local diff.

## Required clinician/owner confirmations for Batch A

- ADHD assessment/testing is currently offered and is appropriate to lead the assessment page.
- Children, adolescents/teens and adults are eligible; identify any minimum ages/restrictions before approving A2/A4.
- Assessments take place at the publicly listed Paoli practice; confirm any in-person/virtual limitations before changing location implications.
- The existing Contact route is suitable and service inquiries can be accepted.
- The retained ADHD article is clinically accurate and suitable to link.

No new statements about licensure, clinician expertise, instruments, cost, insurance, PSYPACT eligibility, turnaround, accommodations acceptance, reviews or outcomes are added. Other public claims should be reviewed separately; they are not validated by this batch.

## Validation completed locally

- Existing .venv imports requests, BeautifulSoup and pandas successfully; no dependency installation was needed.
- The current public homepage, assessment and therapy return 200 with matching canonicals and no observed noindex.
- The proposed assessment/contact/article destinations exist in the saved crawl.
- Current titles, text, headings and exact link targets were extracted from public HTML.
- All eight actions are enumerated and have element-specific rollback; no canonical/URL/robots changes are included.

Not completed: clinician signoff, Elementor widget/export diffs, local WordPress rendering, mobile screenshot review, form/booking tests, SEO metadata graph regeneration, schema/rich-result checks or any remote validation. These are not represented as passing.

## Future local/staging acceptance checks

Before any staging write, obtain sanitized read-only Elementor exports and exact current metadata/widget records. Reconfirm the batch against current staging values and show the final diff with staging-only URLs. Preserve a backed-up copy of affected page/template data and metadata under ignored local/backups.

In an isolated local clone, disable production database/email/forms/booking/analytics connections. Render home and assessment at 390px and a desktop viewport; verify A1–A8, one clear main H1, retained other services, readable headings, keyboard navigation, correct internal routes and no regressions. Test forms only locally with synthetic data and outbound isolation. Match installed PHP/plugin versions; the parent theme must not be overwritten.

On a later explicitly approved staging batch, verify staging installation/path/database separation, page/widget mappings, backups and site protection. Check HTTP/canonicals against the deliberate staging configuration; preserve protective staging noindex. Check menus and corresponding inquiry/article routes. Every import, metadata edit, content change, cache purge and rollback write must be enumerated and approved. No ancillary write is implied by A1–A8.

## Rollback and release boundary

If local rendering fails, discard the local edits and restore the saved local page exports/metadata. For an approved future staging implementation, rollback restores only the reviewed affected widget/content/title/description records and removes A6; unchanged pages/plugins/templates remain outside scope. Obtain explicit approval covering those staging restoration actions, and verify values/rendering afterwards.

Current evidence is a public snapshot, not an adequate database backup. Staging provisioning, transfer configuration and backups are deferred. Keep the disabled uploader, empty deployment map and unset remote identities. Do not generate a release against localhost or production. Never use Push to Live, Full Deploy or Custom Deploy. The agent has no production promotion path; any production release must be independently managed by the owner.

## Later proposals, outside Batch A

- Therapy H1: Individual Therapy → Individual Therapy in Paoli; keep existing local title. Confirm eligibility inconsistency with FAQs first.
- Homepage local positioning: consider a concise Paoli-focused title/hero after owner agrees service priorities; avoid repeating “near me.”
- Contact display: choose and verify the preferred mailbox before aligning visible info@... text and rachael@... mailto, including the footer's extra space.
- Schema: enrich existing #organization only after identity confirmation and integration inspection; no new competing entity.
- Performance and template-sitemap adjustments: gather remaining evidence and review separately.

No approval is requested for incomplete remote actions. This document is the concrete local proposal; implementation remains gated by facts, verified staging identity, final diff and exact human approval.
