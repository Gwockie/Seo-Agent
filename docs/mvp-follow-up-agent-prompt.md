# Follow-up after the multi-site MVP

Prepared October 7, 2026. Start from branch `codex/multi-site-seo-mvp`, or the
main branch once that implementation is merged. Verify Git state before editing.

Recommended model: **GPT-6.1 Sol** (`gpt-6.1-sol`), with **Extra high** (`xhigh`)
intelligence/reasoning. This is a task-specific choice for credential/storage
review, careful migration and evidence interpretation. Official OpenAI guidance
describes Sol as suitable for complex coding and professional work, with `xhigh`
supported: [model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
The [reasoning guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents)
reserves `xhigh`/`max` for especially demanding reasoning. This task does not
authorize spawning agents or creating a separate chat.

## Copyable prompt

Continue this repository's working local multi-site SEO MVP toward a first
verified live audit of the original Paoli practice. The near-term goal is to
return to that practice's discoverability work, with only necessary local app
fixes. Do not rebuild the MVP or add optional integrations.

Read `AGENTS.md`, `README.md`, `docs/implementation-checklist.md`,
`docs/setup-and-migration.md`, `docs/shared-playbook.md`, and
`docs/implementation-agent-prompt.md`. Inspect the existing implementation and
tests. Use `.agents/skills/seo-audit/SKILL.md` when interpreting an explicitly
selected site's evidence; its app-validated profile and saved audit rules are
the source of truth. Load psychology references only for that industry.

The MVP includes four Streamlit views, site-aware SQLite storage, independent
Windows Vault Google connections, one CLI/UI runner, scoped findings/reports,
safe public fetching, legacy registration/migration and credential-free
backup/restore. It passed 45 tests, including the six original tests and four
Streamlit AppTest scenarios, plus a real browser check. Runtime/development
dependencies are pinned and hashed; their October 7 vulnerability scans found
no known advisories. These results are a baseline, not proof of live operation.

At the implementation handoff, this worktree contained no original domain/exact
property, private historical reports, Desktop OAuth JSON or legacy token. The
read-only Windows storage check found ACL access broader than operator/SYSTEM/
Administrators and did not verify EFS or protected BitLocker. Live private writes,
collection, Google setup and backups therefore remain unavailable. A
non-sensitive Windows Vault round-trip succeeded outside the sandbox, but real
OAuth consent/token size/property access were not tested. Vault credentials have
a 2,560-byte UTF-16 payload limit; do not split tokens or use plaintext fallback.

Proceed in this order:

1. Inspect Git/worktree state and the documented local asset paths. Locate
   authorized original-site evidence without printing secrets, moving historical
   files or assuming an account/site identity. Ask for the actual original URL,
   exact property, asset path or protected workspace only where missing. Never
   require the second client's credentials to prove isolation.
2. Review the protection, credential and migration code against the setup guide.
   Diagnose storage and backend availability with read-only checks. Explain
   concrete operator setup steps if needed. Do not silently change ACLs,
   encryption or machine-wide settings, weaken gates, broaden OAuth scopes or
   create private artifacts in unprotected storage. Continue independent local
   review/fixes while live prerequisites are unavailable.
3. Once protected storage and authorized access are available, explicitly create
   the original site's validated profile, seed its ten preserved phrases and
   select its exact connection/property. Have the operator complete OAuth consent.
   Register historical evidence in place. Copy/validate any legacy token only
   into a new unused connection ID; retain the original token unchanged. Treat
   the October 6 indexing fixes as user-reported until supporting evidence confirms
   the actual affected pages/actions.
4. Run a bounded read-only snapshot with priority-page URL Inspection. Inspect
   query/page alignment, indexing/canonicals, service/local relevance and internal
   links using this site's evidence. Distinguish unavailable/partial sources from
   empty exports and zero traffic. Keep property and query/page aggregations
   separate; use final web data, Pacific calendar dates, equal complete windows,
   weighted CTR/position and careful attribution of change observations.
5. Produce `executive-summary.md`, `recommendations.md` and `proposed-edits.md`
   for that audit. Cite its CSV rows and rule versions; prioritize P0 indexing and
   P1 service/local opportunities. Separate on-site findings from unverified
   off-site prominence/competition. Flag clinician confirmations; do not invent
   credentials, services, assessment instruments, insurance, outcomes or reviews.
6. Fix only demonstrated local app defects needed for this workflow. Preserve
   site/account isolation, historical snapshots, legacy CLI compatibility and
   private Git ignores. Run focused regression checks and the full suite after
   material code changes; use AppTest and a browser check for UI changes. Report
   actual checks, remaining blockers and Git state; do not repeat passing checks
   without a new reason.

Website implementation still requires explicit human approval of exact actions.
Do not write to CMS/staging/drafts/autosaves, publish, change DNS/plugins/redirects,
create mass location pages, alter Search Console properties/sitemaps or request
indexing. The only OAuth scope is
`https://www.googleapis.com/auth/webmasters.readonly`. Local proposed edits and
recommendation review state are not approval. Do not upload private evidence or
credentials to GitHub, model providers or other services. Do not add hosting,
scheduling, AI providers, client accounts or conversion integrations.

Finish with the verified original-site findings and five highest-value supported
opportunities, or a precise live-setup handoff if access remains unavailable.
Include reviewable local changes, validation and the next concrete operator step.
Do not claim live migration, indexing improvement or security verification without
evidence. Do not commit or push further work unless the user requests it.
