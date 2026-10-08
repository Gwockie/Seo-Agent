# Preparing local page previews

The app has no CMS writer. Agents can prepare page previews through
`seo_agent.previews.save_preview(store, site_id, audit_id, bundle, revision=1)`.
Use an explicitly selected validated site/audit and protected storage. New revisions
are numbered 1–20; each artifact is created exclusively. Earlier captures must
remain unchanged. The newest revision is initially shown, with older revisions
available in the app. Backups and audit packets include these known artifacts.

Read and write capture JSON explicitly as UTF-8. Windows' default text encoding
can corrupt punctuation before rendering. If a saved supplement needs correction,
prepare a new revision from the original capture and preserve earlier revisions.

A bundle has `schema: 1`, matching `site_id`/`audit_id`, a validated site `appearance`,
a bounded map of public image URLs to local raster data URIs, and 1–6 `pages`.
Each page contains its exact public URL/title, UTC capture date, viewport width,
captured tree and 1–20 exact proposed actions. A node has a supported tag, unique
`r<number>` ID, computed-style dictionary and children. Text nodes contain only
`text`; image nodes can also include their observed `src`/`alt`; links their
observed `href`. Capture only public DOM/appearance data, without cookies,
credentials, browser storage, analytics requests or patient data.

Actions use `kind` (`text`, `title`, `href`), `current`, `proposed`, `rationale`,
`confirmations`, `validation` and `rollback`. Text/link actions identify an exact
`node_id`. Text actions may identify a direct `text_child` index to retain sibling
headings and markup. The current value must match the captured value; text needs
exactly one occurrence. Missing or overlapping targets are rejected. Do not invent
an insertion point for additions whose current placement has not been verified.

Use bounded read-only public fetching or a user-authorized public browser capture.
Capture actual computed styles and visible content at a known viewport. A normal
browser capture does not resolve an automated crawl failure, prove response headers
or complete SEO collection. Label the source limits and preserve the audit manifest.
Do not solve challenges or alter hosting/security merely to obtain a preview.

`seo_agent.appearance.save_appearance` accepts only validated per-site palette and
typography data. `font_asset` accepts bounded WOFF/WOFF2; `raster_asset` accepts
bounded PNG/JPEG/WebP. Save fonts/images as local data, never active external assets.
The renderer generates allowlisted inert HTML, escapes source text, strips active
links/forms/scripts/embeds, sanitizes computed properties and discards external CSS
URLs. The inner iframe has an empty sandbox and a content policy forbidding scripts,
network connections, navigation bases and form actions. Never pass raw imported
HTML or website scripts to Streamlit iframe APIs.

Validate through `load_preview` before displaying a bundle. Factual confirmations
and exact production approval remain separate from preview revisions. For an actual
staging environment, follow `website-change-policy.md`; local previews do not verify
CMS behavior or authorize production deployment.
