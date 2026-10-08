# Guided setup and a local learning journal

Setup uses editable lists rather than JSON entry. Main fields have help tooltips.
Click a table cell to edit it, add a row at the bottom or select a row to delete,
then use the matching Save button.

- **Services and related search terms:** one term per row; repeat the service
  group for synonyms. Existing group names connect to target phrases.
- **Confirmed business facts:** a fact name and its confirmed value. Leave
  uncertain claims out and never enter patient/customer records.
- **Brand aliases:** business-name variants, one per line, for distinguishing
  branded searches from relevant new discovery.
- **Intentionally excluded URLs:** pages deliberately excluded from indexing
  recommendations. This list is not a crawl blocklist.
- **Advanced audit options:** controls for rule enablement, minimum impressions
  and CTR percentage. Leave unused cells empty. Psychology's clinical confirmation
  cannot be disabled.

Existing website/property identities stay fixed. A different identity needs a
separate site with independent account references and history. Target phrases
also have an editable table. Saving affects future audits; earlier snapshots
retain their original profiles and evidence.

A fresh session with one saved site opens its review view when it has audits.
Multiple sites still require selection. Navigation is session state; saved
settings, evidence, page copies, plans and reviews live on disk and survive restart.

## Explanations and tracking

Prepared proposals show **Why it is recommended**, **What we expect** and **How we
will check**, alongside exact values, factual confirmations, validation and
rollback. Rationale comes from the saved proposal. Expected effects are generic
hypotheses about the type of change, not a newly verified diagnosis or a ranking
promise. Automated findings present saved evidence and measurements similarly.

**Prepare a tracking plan** opens Changes & results with the explanation and
baseline audit. Review and save the plan. This does not approve, publish or change
audit rules.

1. Save the hypothesis, exact values, affected page and primary outcome.
2. After a separately approved change is actually published, record its Pacific
   reporting date and evidence. This remains user-reported; an approval reference
   typed here is not independent authorization. An existing record must identify
   the exact affected page before it can supply that plan's publication date.
3. Select a follow-up audit. Automatic comparisons require complete final
   web-search metadata, equal-length Pacific reporting windows, a baseline ending
   before publication and a follow-up starting after it. Opening this view does
   not collect new live data.
4. Save a lesson or uncertainty. Reviews append; earlier reviews and baseline
   evidence remain intact.

Page metrics use the exact page's byPage rows. Relevant non-branded impressions
use visible query rows, freezing the baseline's brand/target definitions for both
periods. Missing rows are unknown, not zero. Indexing, correct landing pages and
factual/user-experience outcomes need direct review; traffic cannot verify them.
CTR differences are percentage points; lower position values mean a better
observed average position. Neither proves an edit caused the difference.

Other recorded changes in the measured periods are shown as possible explanations.
Query privacy/top-row limits, small samples, changing demand and competition also
limit conclusions. Saved lessons can inform the user and an authorized local
agent's future recommendations. No AI provider, automatic rule tuning or website
implementation was added. Site-scoped CSV downloads escape spreadsheet formulas.
Streamlit's built-in CSV button is disabled because editable cells contain literal
text; use the app's labeled CSV downloads instead. Table editing and copy/paste
remain available. This is an export safeguard, not an access-control boundary.
Protected backups include the journal; older backups restore with an empty one.
Restored Google selections remain detached.

## Navigation performance

The earlier app duplicated recursive Windows access checks and queried BitLocker
on normal reruns despite encryption being optional. The optimized path keeps a
fresh recursive ACL/reparse check on every rerun and every write, reuses it only
within its current rerun, and queries BitLocker for an explicit
`storage-check --require-encryption` request. No permission result is cached
between reruns and no permissions were changed.

On the configured workspace, the protection call fell from 6.517 to 1.937 seconds
and Store opening from 14.350 to 1.798 seconds. These are component measurements;
rendering and larger folders take additional time. Read-only Google access and
exact production approval remain unchanged.

Validation: 97 tests passed, including fourteen Streamlit AppTest scenarios and
checks for persistence, site isolation, comparable/unknown outcomes, clinical
guards, fresh permission checks and old/new backup restore compatibility.
