# Public performance and asset evidence

Tracked public-only copy of the October 5 audit. Raw HTML/assets and future private Search Console exports remain ignored under data/ and reports/. This is a historical baseline, not current account data.

October 5, 2026. Compare homepage, assessment and individual therapy. This file separates source evidence, limited HTTP timings and missing browser/field measurements.

## What was actually measured

| Page | Linked stylesheets | External script tags | Image tags | Saved HTML bytes | Downloaded CSS decoded bytes | Downloaded JS decoded bytes |
|---|---:|---:|---:|---:|---:|---:|
| Home | 44 | 27 | 10 | 139,393 | 921,107 | 557,131 |
| Assessment | 34 | 25 | 2 | 127,447 | 688,809 | 407,902 |
| Individual therapy | 32 | 25 | 3 | 116,659 | 671,785 | 407,902 |

Sources: pages.json, asset-measurements.json and saved HTML. All linked stylesheets counted here are in the head. Counts describe HTML declarations, not measured browser requests or proof of unused assets. Byte sums use downloaded first-party URLs and decompressed responses; exclude the external Google tag, font files, CSS background images, dynamic imports and other runtime requests. Responsive image transfer and lazy loading were not measured. They are not compressed network transfer totals.

The union across these pages is 86 asset URLs: 85 first-party assets downloaded successfully and one external Google tag recorded without downloading. Public source is under data/.../assets. Asset inventory CSV includes page scope, HTML ID/handle hints, URL, flags, observed jQuery/Elementor lexical references and unresolved dependency fields.

## Theme/plugin observations

- Public Hello Elementor style.css identifies version 3.4.4 and matching assets load on the pages. This verifies the public parent-theme stylesheet version, not child-theme activation or PHP version.
- Elementor generator/assets report 4.2.4. Elementor Pro asset URLs report 3.29.2. Pro code is present in the rendered output; a current license/subscription, actual installed inventory and compatibility status have not been inspected.
- ElementsKit Lite URLs report 4.0.6; Contact Form 7 URLs report 6.1.7; Ultimate Blocks style URL reports 3.6.0. Sliderberg and Gutenberg resources also load.
- Site Kit generator reports 1.188.0; Rank Math PRO identifies itself in page comments and Rank Math generates the sitemaps. Treat these as public output evidence, not a complete active-plugin list or verified licenses.
- WordPress generator reports 7.1.2; installed admin/PHP versions remain unverified. Query-string versions can be cache labels or stale output.
- Robots.txt mentions a wpo plugin-table JSON path. This is a WP-Optimize-related clue, not proof that any specific optimization/caching setting is active.
- No child-theme URL was found on these pages. That absence does not prove there is no child theme.
- PHP functions.php/enqueue registrations, dependency arrays, template exports, inline optimizer settings and cache configuration are unavailable. Do not infer those from file names.

## Concrete front-end candidates

1. **Global asset scope:** all three pages load CF7 CSS, swv, CF7 JS and Site Kit CF7/WPForms event-provider files despite having no form tags. Investigate scope and dynamic form/popup dependencies; source evidence is not yet permission or sufficient support to dequeue them.
2. **Widgets and duplicate capabilities:** ElementsKit common CSS is 158,448 decoded bytes, icon CSS 83,510; Ultimate Blocks CSS 83,892 and Sliderberg CSS also load on these Elementor pages. Establish actual widget use and render cost through a waterfall/coverage review and source dependencies first.
3. **Fonts:** the linked local Roboto CSS file is 109,188 decoded bytes. Check loaded faces/weights/subsets and font requests before proposing pruning. A large CSS file does not establish all its fonts are transferred.
4. **Images:** one lazy homepage PNG source is 1,562,804 bytes; hero/header PNG source is 154,058 bytes. Responsive/lazy markup exists. Determine actual mobile currentSrc/LCP element and transferred bytes before preparing approved image variants or changing priority/loading. Do not assume the lazy image is LCP or remove its lazy loading.
5. **Script execution:** jQuery/migrate, Elementor runtime/modules, Pro/SmartMenus and ElementsKit menus are dependencies of functional UI. Most script tags do not carry async/defer; Site Kit event scripts have defer, Google tag is async. Footer execution and dependency order require inspection; no blanket delay/dequeue is proposed.

These candidates can affect rendering or data cost; none is proven to be the dominant bottleneck. Hello's own files are only part of the page.

## HTTP samples and server limits

Three sequential GETs per page, one reused requests session, no CPU/network throttle, no cache-busting and no server writes. Data: http-timings.json.

| Page | Response-header time range | Median | Total HTML download range |
|---|---:|---:|---:|
| Home | 42.0–43.9 ms | 42.0 ms | 53.2–62.2 ms |
| Assessment | 43.6–57.8 ms | 49.8 ms | 48.7–58.9 ms |
| Therapy | 48.6–59.8 ms | 49.3 ms | 49.7–61.0 ms |

These local-client numbers include its network/TLS/proxy conditions and may benefit from connection reuse or intermediary caching. They are neither pure PHP time nor mobile browser TTFB. Responses expose nginx, gzip, Cache-Control: no-cache, X-Proxy-Cache: MISS and X-Proxy-Cache-Info. These do not establish origin saturation, SiteGround resource ceilings or all caching layers.

No PHP/database profiler, server resource history, uncached authenticated timing or multi-region repeated origin measurements is available. Keep StartUp; the available evidence does not justify a hosting upgrade.

## Missing mobile evidence and failed attempts

- Mobile PageSpeed API attempted for all three URLs on October 5, 2026 around 16:42 EDT. All returned HTTP 429 RESOURCE_EXHAUSTED quota errors. Recorded in psi-attempts.json. No Lighthouse results or CrUX results were returned.
- An existing Playwright runtime and installed Edge were used for one attempted headless mobile-viewport launch. Edge exited before any navigation. No screenshots, mobile waterfall, layout review or browser metrics were generated. Do not report a successful mobile run.
- No earlier dated PSI/Lighthouse/CrUX reports were present. No measured LCP, INP, CLS, FCP or TBT, and no pass/fail CWV verdict.
- No complete dependency graph or controlled before/after code test. No optimization code is appropriate yet.

## Repeatable measurement and validation plan

1. Collect field mobile LCP/INP/CLS from available read-only CrUX/PSI or Search Console CWV reports; explicitly record whether URL-level or origin-level, date/window and sample availability. Absence of field data is not a pass.
2. For each of the three URLs, run at least three comparable mobile Lighthouse navigation tests on the same machine/browser/version/location with a recorded preset (for example, standard mobile simulated throttling). Record URL, UTC timestamp, viewport, cache state, network/CPU settings and median/range.
3. Save reports and a network waterfall. Inspect main-document latency, render-blocking CSS, font requests, image currentSrc and LCP element, main-thread long tasks and runtime widget loading. Record compressed transfer bytes separately from decoded source bytes. Test both fresh and warm browser caches under consistent conditions.
4. Compare LCP loading phases and server latency before assigning a hosting cause. Repeat from more than one representative network/time period if server latency appears dominant; obtain owner's read-only resource-limit evidence before revisiting a plan.
5. Inspect actual enqueue code/handles/dependencies, inline configs, Elementor exports and existing optimizer settings. Draft one small supported local change in src/optimization only after that inspection. Do not blindly remove jQuery or delay forms/consent/menus.
6. In an isolated local clone, test menu/focus, contact/booking and consent with synthetic data and blocked production integrations. Re-run the same lab setup. Record differences in local server/network conditions; local speed cannot establish production hosting speed.
7. Any later staging patch/import/setting/cache purge needs its own current/proposed exact review and explicit approval. Keep staging noindex/protection. Read-only production field verification can follow an independently managed release.

Google's field targets are LCP ≤2.5 seconds, INP ≤200 ms and CLS ≤0.1 at the 75th percentile, segmented by device. Lab testing helps diagnosis and regression checks but is not a substitute for field data; Lighthouse TBT is not INP. [Google Web Vitals documentation](https://web.dev/articles/vitals).
