# Local release preparation and staging transfer blueprint

Status: local preparation is usable; remote transfer is intentionally disabled.
`Upload-Staging.ps1.example` always stops before network access. It is a placeholder,
not an operational uploader or a security boundary imposed on SiteGround itself.
There is no deployment workflow on push and no upload-on-save integration.

Current decision: keep StartUp and defer the quoted $13/month upgrade. This is a
future staging blueprint, not a prerequisite for local work. Use
`docs/LOCAL_DEVELOPMENT.md` for audits, source validation and local WordPress testing.
Do not invent remote paths or fill staging variables with a localhost/production
target to make `prepare_staging.py` run. The preparer intentionally requires an
actual declared staging target; local drafts do not need a staging release package.
The empty map and disabled transfer remain in place until remote staging is chosen.

## Prepare a reviewable release

1. Follow `docs/STAGING_SETUP.md`. Record actual staging/production URLs and physical
   roots, SSH connection details, active theme, and a staging-only recovery route.
2. Copy `staging.example.json` to ignored `staging.local.json`. Set its environment
   references in your shell; `.env.staging.example` is documentation, not a loader.
3. After inspecting the actual child theme, add ONLY the reviewed code to `src/`.
   Map each deployable source explicitly to a path relative to that theme directory.
   The initial empty map is intentional: there is no verified website code yet.
4. Run:

   ```powershell
   .\.venv\Scripts\python.exe scripts/prepare_staging.py --config deploy/staging.local.json
   ```

   The tool uses only Python's standard library. It creates a fresh ignored
   `dist/staging/<release>/` with `payload/`, `manifest.json`, `manifest.sha256`, and
   `review.md`. JSON is parsed strictly; mapped PHP requires successful local
   `php -l`. JS/CSS/HTML are hashed but require separate syntax/functional checks.
   JSON parsing is not Schema.org or Google eligibility validation.
5. Fill in `review.md` with actual current bytes/hash or verified absence, diffs,
   affected staging URLs, clinical confirmations, validation, integration steps,
   exact ancillary actions, and rollback. Archive that review and human approval
   locally. Any changed payload or destination requires a newly reviewed release.
6. Present the concrete batch and wait for human approval. Only then implement
   and run a transfer that meets ALL checks in `Upload-Staging.ps1.example`.
   A file named `approval.json` or a flag set by an agent does not establish approval.

Example mapping shape (illustrative; do not copy unverified code into the theme):

```json
{
  "source": "src/schema/localbusiness.json",
  "target": "assets/schema/localbusiness.json"
}
```

Schema JSON requires a reviewed PHP loader. A PHP snippet requires a reviewed
include/hook; a page template requires appropriate staging template assignment.
Those integration edits and WordPress settings are separate exact actions in the
same approval batch. Never replace `functions.php` with an isolated snippet.

## Transfer and recovery requirements

The offline preparer rejects unsafe local/relative paths, duplicate or colliding
targets, equal hostnames, overlapping declared roots, non-staging configuration,
and attempts to enable remote writes. It cannot verify server identities, remote
symlinks, hard links, DB separation, current remote hashes, permissions or user consent.
Those are prerequisites for the future read-only preflight and approved uploader.

Use key authentication and pinned host keys. Use the actual SSH host from Site Tools;
it can serve both staging and production. Check physical paths and installation
identity rather than relying on the hostname or key name. SiteGround SSH keys can
access all files for a site; a dedicated staging installation/account gives stronger
isolation than a staging folder under the same credential.

Back up every replaced staging file BEFORE upload. The review must specify how
new files would be removed and old files restored if needed; obtain explicit
approval for these rollback writes. SFTP can leave a partially updated release;
stop on failures, record changed files, and restore only that reviewed staging batch.
Never restore an entire hosting account to fix a staging code issue.

Secrets, downloaded theme files, backups, release artifacts and reviews stay local.
Use `git check-ignore` before committing. No secrets belong in source, prompts,
workflow logs or reports. A future GitHub Actions uploader would require a manual
dispatch, exact release hash and a protected staging environment with human review;
do not add deployment secrets or unattended transfers during this setup.
