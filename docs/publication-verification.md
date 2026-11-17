# Publication verification from saved captures

Run the report with an explicit expectations file. It reads the existing workspace
and prints JSON to standard output.

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent --workspace "path\to\workspace" publication-verification expectations.json
```

This synthetic declaration shows the supported effect kinds. Replace the IDs with
the selected site's ID and the exact saved public snapshot IDs for each URL.
The **Tracked pages and check settings** panel lists recent snapshot IDs alongside
their URLs, capture times and source status.
Declare every affected URL separately, including other pages with relevant shared
navigation. Add one entry per expected element and repeat the value on both sides
when you expect it to stay the same.

```json
{
  "schema_version": "seo-publication-expectations/1",
  "site_id": "11111111111111111111111111111111",
  "pages": [
    {
      "url": "https://example.com/services/",
      "before_snapshot_id": "22222222222222222222222222222222",
      "after_snapshot_id": "33333333333333333333333333333333",
      "effects": [
        {"kind": "heading", "selector": "main > h1", "before": "Services", "after": "Our services"},
        {"kind": "breadcrumb", "selector": "#breadcrumbs > span.current", "before": "Services", "after": "Our services"},
        {"kind": "navigation_label", "selector": "#primary a[href='/services/']", "before": "Services", "after": "Our services"},
        {"kind": "document_title", "before": "Services | Example", "after": "Our services | Example"},
        {"kind": "canonical", "before": "https://example.com/services/", "after": "https://example.com/services/"},
        {"kind": "robots", "before": "index, follow", "after": "index, follow"},
        {"kind": "googlebot", "before": "noarchive", "after": "noarchive"},
        {"kind": "x_robots_tag", "before": "", "after": ""}
      ]
    }
  ]
}
```

Use a CSS selector that resolves to exactly one static body element in each
capture. Use an `h1`–`h6` element for a heading. The report checks
the selected element's body path and attributes across captures. Changes to
that location evidence leave the pair unavailable. Text comparisons preserve
case and collapse presentation whitespace. Canonical values are the captured
`href` strings, so declare a relative value as relative if that is what the
page emits. Directive values are compared as captured. An explicitly saved
empty `X-Robots-Tag` field is observable. Missing fields, missing or duplicate
elements, unusable captures, and incomparable pairs are unavailable.

Each row includes the expected and observed values and a status of
`matches_expectation`, `mismatch`, or `unavailable`. A match requires both
observations to equal their respective expected values. The report includes a
SHA-256 digest of the validated declaration and the exact snapshot IDs. For
resolved captures, it also includes capture times, source status and record
digests. The command reads saved HTML and headers only. It performs no network
requests or journal writes. Its results describe static public evidence within
the declared scope. Browser behavior, Google indexing, CMS state, authorship
and publication authorization remain outside that scope.

## In-app screen

Select the site in the sidebar, then open **Publication verification**. Enter each
exact page URL, select its before and after captures, and enter the expected effects.
The capture choices show IDs, UTC capture times and saved source status. Neither
capture is selected automatically. Increase the page/effect counts to add explicit
scope; reduce them to remove entries. Shared effects on other pages must be declared
separately. No completeness of shared scope is inferred.

Import the same JSON format using a file or pasted JSON, or download the current
validated form as expectations JSON. Imports for a different site are rejected.
Missing imported capture references stay explicit and are reported as unavailable;
they are never replaced with a newer capture. Run the read-only verifier to see
expected and observed values grouped by URL, including explanations for unavailable
comparisons. The report download contains the verifier's exact capture references,
record digests and expectations digest. Editing the form hides the prior result and
its download until the verifier runs again.

The form and report live only in the current app session. Site switching clears the
previous site's form and report. Download any evidence you need to retain. This
screen reads saved captures through a read-only store, does not refresh tracking,
and does not save approvals, receipts, reconciliation or rollback records. A match
is evidence within the declared static scope, not publication permission or a
verified CMS receipt.
