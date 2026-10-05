# Schema source

Place confirmed JSON-LD here after running `prompts/schema.md`. Planned output:
`localbusiness.json`. No fabricated practice record or executable schema is included
in the initial scaffold. Store clinician confirmations in ignored reports, not a
public facts file. Omit unknown optional fields and report missing required facts.

Inspect existing plugin/theme schema and use one consistent entity graph. A reviewed
loader under `src/theme/` must actually render the JSON-LD; do not upload this README.
Validate syntax, Schema.org semantics, applicable Google requirements, visible-content
consistency and locally rendered HTML when a clone is available. Remote staging
HTML checks remain deferred until staging is provisioned and the exact release approved.
