# Staging release review hook

Deferred workflow: the owner currently retains StartUp and prioritizes the audit
and local drafts in docs/LOCAL_DEVELOPMENT.md. Do not request staging credentials
or prepare a remote release until the owner chooses an actual staging route.

Follow AGENTS.md. Read deploy/README.md and docs/STAGING_SETUP.md. Prepare locally.
Inspect the explicit release payload and manifest; never treat a hash or an agent's
statement as human approval. Reconcile every code edit and ancillary remote action.

For each affected file/URL/setting show current value, proposed value/diff, intended
action, factual confirmation, validation evidence and exact rollback. Verify target
identity and physical path isolation with read-only evidence before proposing transfer.
Exclude secrets, patient data, reports, databases and unmapped files.

Present a complete reviewable batch. Wait for the human's explicit approval of its
exact actions before any staging write. Keep production prohibited. If bytes, target
or scope changes, prepare a new review. Rollback writes also require exact approval.
