# Tracking validation — October 8, 2026

Validated in the isolated `codex/automatic-change-tracking` worktree based on
main `85e27ac86b7712bc051f5b53ecc9214da23366aa`, using Python 3.13 and this
repository's hash-pinned development lockfile in `.venv-tracking`.

## Automated checks

The initial implementation's full suite passed **131 tests**, including **18 Streamlit AppTest
scenarios**. The earlier 97-test baseline is not counted as independent proof.
The additional tracking coverage uses only generated sites, synthetic website
responses and synthetic Google exports, and checks:

- Strict inert handoff import, duplicate keys, same-import idempotence, missing
  values, invalid timestamps, traversals and own-audit evidence row validation.
- Imported assertions versus explicit human UI approval; immutable exact batches;
  revision/current-value invalidation, including a value returning to its old text;
  unaffected action scope and no website implementation from an approval.
- Attempt/outcome ordering, duplicate/replayed IDs and events, pending attempts,
  partial/failure retention, append-only correction/rollback, explicit public
  snapshot verification, action/revision/site isolation and restart persistence.
- Exact outside diffs, unknown author/publication time, observation intervals,
  failed/HTTP 202/challenged sources, preserved baselines, whitespace/script
  normalization, preserved dates/prices and URL-prefix/robots redirect boundaries.
- Persistent source selection for overlapping audits, distinct property/page
  aggregation, CTR recalculation, weighted aggregate metric math, missing metrics
  and rows, line segments across gaps, immutable earlier sources and source IDs.
- Shared audit/check/backup lock exclusion, concurrent receipt replay, persistent
  refresh throttling, rerun request deduplication and bounded tracking settings.
- Fresh protected write/export gates, literal browser rendering, formula-safe
  CSV, source-scoped ZIP supplements, original/version 1/version 2 backup restore,
  exact restored trend provenance and approval history detached from authority.

Commands run:

```powershell
.\.venv-tracking\Scripts\python.exe -m unittest tests.test_tracking tests.test_tracking_ui -v
.\.venv-tracking\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-tracking\Scripts\python.exe -m compileall -q seo_agent app.py
.\.venv-tracking\Scripts\python.exe -m pip check
git diff --check
```

Dependency check reported **No broken requirements found**; compilation and diff
whitespace checks passed. CLI help was checked for `import-handoff`,
`record-receipt` and `tracking-refresh`. Receipt writes were exercised through the
Python interface with synthetic Stores; a real protected client CLI write was not
performed. Initial sandboxed AppTest execution stalled in Python's local
socket-pair initialization. Those isolated test processes were stopped and the
suite was rerun successfully with local socket access. No primary app was stopped.

## Real browser smoke check

The Codex in-app browser used a separate synthetic workspace
`workspace/tracking-smoke` on **127.0.0.1:8513**. It exercised site selection,
Recommendations & changes, selecting/freezing an exact proposal, inspecting the
frozen values and the separate human authorization controls, Changes & results,
whole-site/page selection, CTR selection, the outside marker's literal before/
after and UTC uncertainty interval, and the missing-page-data state. No approval
was submitted in that browser. Automated human-input cases are synthetic AppTests.

The synthetic Google fixture intentionally returns sparse rows. Its tracked page
has no visible daily row, so that browser scenario validates an **unknown** page
metric, not a measured zero or a live improvement. Daily page values and complete
math are independently covered by synthetic source tests. Browser screenshots
remain ignored local artifacts; no client evidence or screenshots were published.

## What is not certified

No primary private database was opened/migrated, ignored private assets copied,
Google/WordPress client credentials loaded, live audit run, external page fetched
for this validation, or primary app on port 8502 restarted. The tests do not prove
live Search Console quota/access, actual WordPress execution, CSS/JavaScript page
rendering, hosted staging isolation, a production rollout or an SEO benefit.

The existing reviewed public-fetch and credential tests remain passing. The
Search Console scope is unchanged. A separately authorized WordPress step and
fresh factual/current-value review remain required for website implementation.
Primary rollout waits for idle live jobs and a verified protected pre-migration
backup, as described in `automatic-change-tracking.md`.

## Independent review fixes

A subsequent review reproduced three defects: a heading/link value surviving in
another location kept approval usable; a changed actual value in a failed receipt
allowed retry with the same approval; and restored receipt column/payload action
identities could disagree. The fixes bind frozen text/link targets to saved preview
structure, reject contradictory failed outcomes and block historical reuse, and
validate restored receipt action/revision identities. Target bindings also apply
to public verification and are validated on restore. Older untargeted batches
remain history but cannot authorize new text/link work.

The full suite after these fixes passed **142 tests in 111.811 seconds**, including
**19 AppTest scenarios**. Eleven additional regressions cover moved headings,
direct text-child slots and links, hierarchy ambiguity versus harmless whitespace/
scripts, wrong-location public verification, target backup restoration, partial
failure versus eligible unchanged retries, historical contradictory failures,
receipt action/revision mismatches and disabled stale-target human approval in UI.
Compilation and whitespace checks passed.

A new real-browser smoke check used only `workspace/tracking-fix-smoke` on
127.0.0.1:8513. A synthetic captured H1 was changed while its original text moved
to the footer. The browser showed the text action and frozen human approval
disabled, with the stale-action warning. No approval was submitted and no browser
console errors were reported. The screenshot stays in ignored local artifacts;
the temporary development server is separate from the primary app.

The independent reviewer confirmed all three findings are addressed and reported
no additional actionable defect in the fixes. Its separate run passed **35
tracking tests**, plus a synthetic relative-link/proposed-verification probe.
That independent count overlaps the full suite; it is not additional coverage.
Browser-captured versus static HTML structure may differ. Target matching fails
closed in that case; a fresh matching capture/review is required. This does not
certify the feature as bug free or validate live rollout.
