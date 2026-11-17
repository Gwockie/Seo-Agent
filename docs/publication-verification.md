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
capture. Use an `h1`–`h6` element for a heading. Text comparisons preserve
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
