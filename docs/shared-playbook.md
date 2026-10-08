# Reviewed mechanisms — version 1.0

This trusted playbook contains mechanisms, not client facts or conclusions. It is
not an executable import. Rule IDs and applicability come from `config.py`.

| Mechanism | Scope | Prerequisites | Limits/exceptions | Validation |
| --- | --- | --- | --- | --- |
| Indexing restriction review (`indexing` 1.0) | General | Own priority page's directive or Google inspection row | Intentional exclusions; inspection dates may lag | Fresh read-only inspection after approved correction |
| Canonical review (`canonical` 1.0) | General | Own intended page and canonical evidence | Deliberate duplicate URLs can be valid | Compare user/Google canonical and internal links |
| Link repair review (`broken_link` 1.0) | General | Own source link plus actually fetched 404/410 destination | Crawl sample is incomplete | Re-fetch the approved source/destination |
| Landing-page alignment (`alignment` 1.0) | General | Own query/page observations and configured intended page | Multiple pages do not establish cannibalization | Equal complete windows, same aggregation |
| Clinical content review (`clinical_review` 1.0) | Psychology service context | Own-site service relevance evidence | No invented qualifications, instruments, insurance or outcomes | Clinician confirms facts before exact-action approval |

Promote outcome lessons only after removing client names/domains/copy, reviewing
prerequisites, exceptions and evidence strength, and explicitly reviewing the
general lesson. An observed improvement does not establish causality. A receiving
site needs its own matching evidence. No cross-client retrieval or learning job
exists in this MVP. No lesson carries permission to publish.
