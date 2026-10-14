# Elementor compatibility work

Elementor headings and WordPress core headings have different storage and save
contracts. The version 1 publisher edits an anchored core heading in `post_content`.
Elementor stores layout and controls as private WordPress post metadata. Its heading
widget has a title control, separate from `post_title` and SEO plugin metadata.
See [Elementor storage](https://developers.elementor.com/docs/data-structure/) and
[widget controls](https://developers.elementor.com/docs/data-structure/widget-element/).

The software must support the existing site configuration. Do not change a live
theme, disable plugins, add anchors, alter excerpts or convert builder content to
make the current core-block adapter accept it.

## Implemented local preparation

The app's [Hosting & CMS workflow](cms-discovery.md) now saves site/environment
connections, read-only REST evidence and protected administrator assertions. Its
offline preparation UI cross-checks imported page/widget metadata against separately
collected REST identities and rendering, retaining provenance and freshness. It
does not certify Elementor publication or enable a writer.

`seo_agent.elementor` provides offline mapping of one explicit static heading in a
raw Elementor metadata array. It accepts nested container/section/column elements,
requires a unique widget identity and explicit heading level, records ancestor ids
and the exact title path, and fingerprints the complete source document.

`preview_heading` generates a local candidate by replacing only the JSON string
token for that title. It preserves every character outside that token, including
formatting and sibling values. A fresh whole-document fingerprint and mapping must
match. Unicode and entity-looking text are literal; reverse previews restore the
old semantic value (the original token's escape spelling may differ).

`bind_rendered_heading` cross-checks the independently supplied CMS page id, unique
widget and ancestor ids, heading type/level and literal text against the public
page document. Public selectors never supply a CMS identity. Nested document
boundaries cannot claim page-local headings; unrelated sibling header/footer
documents are permitted as surrounding evidence, without certifying their effects.
Duplicate identities/JSON keys, dynamic/global/template references, rich/linked
headings, malformed/bounded-out data and stale documents are rejected.

Example using synthetic or protected read-only evidence:

```python
from seo_agent.elementor import map_heading, preview_heading, bind_rendered_heading

mapping = map_heading(raw_metadata, page_id=9001, element_id="heading1")
bind_rendered_heading(captured_public_html, mapping)
local_candidate = preview_heading(raw_metadata, mapping, "Synthetic revised heading")
```

These mapping functions contain no network access, CMS writes, credential handling,
database changes or approval handlers. The discovery workflow saves their inert
results separately; they are not wired into the publication executor.
Successful mapping reports `publishing_compatible=False`: it cannot establish
site/plugin/host compatibility or grant publication permission. The core adapter's
server rejection remains intact. No Elementor production writer is enabled yet.

## Evidence required to complete the writer

For the selected installation obtain an existing read-only host route or an
administrator-prepared protected export of:

- The exact published page id/URL/raw row, excerpt and relevant metadata; the
  actual metadata row/key/element path must be independently proven.
- Core/PHP/database and theme/plugin versions, MU plugins/drop-ins, file checksums,
  active Elementor experiments and page/template/kit/global reference conditions.
- Elementor's pinned save/render/cache lifecycle, mirrored `post_content`, generated
  excerpt/snippet behavior, object/element/page caches and host/CDN invalidation.
- Host credentials/deployment/job/mail/synchronization isolation evidence for staging.

Do not export secrets, customer submissions or arbitrary credential-bearing options.
Do not enter a production autosaving editor to collect evidence. Preparing this
module does not authorize installing a production inspection plugin.

The next adapter must certify an explicit stack and define atomic field changes,
metadata/content mirrors, timestamps, cache effects, journal recovery and inverse
rollback. Do not replace this work with generic REST content/metadata writes or a
global cache flush. Elementor's [CSS flush documentation](https://developers.elementor.com/docs/cli/flush-css/)
describes broad effects that must not be hidden inside a single heading approval.

Preserve exact frozen proposal and separate CMS human approvals, fresh destination
and full dependency checks, durable attempts and stable installation identity,
duplicate suppression, read-only reconciliation before retry, immutable known
success, independent write/verification outcomes, explicitly approved rollback and
backup/restore protections. Search Console remains `webmasters.readonly`.

Implement the certified server/client/UI extension with synthetic loopback fixtures
and a reviewable PR, validate on verified isolated staging, then obtain separate
exact production setup and publication approvals. Local mapping tests alone do not
certify an installed Elementor version or authorize a production pilot.
