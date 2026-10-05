# SiteGround staging and SSH setup walkthrough

Status: deferred reference. The owner chose to retain StartUp and defer the quoted
$13/month ($156/year) upgrade. Start with `LOCAL_DEVELOPMENT.md`; no staging purchase
or SSH setup is required to audit the public site or prepare local source files.

This is a guide for the owner. Architecture setup has not created a staging site,
registered keys, changed DNS/settings, or connected to SiteGround. The agent may
perform staging writes only after approval of the exact actions in a concrete review.
Production writes are prohibited. Do not click Push to Live, Full Deploy or Custom Deploy.

## Current practice setup and StartUp decision

- Public URL: https://meadowandmindpsychology.com/ (owner supplied).
- Active theme: Hello Elementor (owner reported).
- Hosting tier: apparently StartUp; confirm the actual tier in the account.

[SiteGround's current plan comparison](https://www.siteground.com/wordpress-hosting.htm)
includes SSH on StartUp but reserves built-in staging for GrowBig and GoGeek.
If your account says StartUp, the staging tutorial you opened describes a feature
that your current tier does not include. SSH access alone does not provide a clone.

The active route is local development; remote staging is a future option:

1. Keep StartUp and begin with a local WordPress copy. Obtain authorized exports
   read-only, minimize sensitive records, match PHP/plugins, and keep the clone local
   with outbound email/form integrations disabled. Confirm export mechanics before
   using a plugin that might write to production. There is no SFTP staging target yet.
2. Later, if justified, have the owner review the account's actual upgrade and renewal cost for GrowBig.
   If the owner chooses and completes that upgrade, use the built-in staging steps
   below. No purchase or plan change is performed by this guide.

Use route 1 now. Reconsider route 2 only if measured server constraints or recurring
staging work make the cost worthwhile. Staging and fresh on-demand backups are
workflow benefits; no measured speed or ranking gain has been established for this
practice by a plan upgrade. Do not install a staging plugin or create a second
installation inside the production root as a workaround during this setup.

Hello Elementor is the active parent-theme name supplied by the owner. Confirm
the actual theme directory/version and whether any child theme exists before mapping
code. Keep `SG_STAGING_THEME_SLUG` unset until the intended staging integration target
is verified. Elementor page/template import and assignment are WordPress writes;
SFTP theme-file uploads alone cannot apply an Elementor template. See
[Elementor's template import/export documentation](https://elementor.com/help/template-library/).

## Deferred step 1. Create the staging copy in Site Tools

1. Sign in to SiteGround. Select **Websites**, find the practice site, and open
   **Site Tools**. Confirm you have selected the correct practice/domain.
2. Open **WordPress > Staging**. SiteGround documents staging on GrowBig, GoGeek
   and Cloud plans. If the option is absent, confirm your plan/installation with
   SiteGround before purchasing anything or installing a staging plugin.
3. Select the WordPress installation. Give the copy an identifiable development
   name, such as `seo-development`, and choose **Create**. Review any requested
   additional files; include only assets the site needs. Creation copies the files
   and database, so consider whether sensitive form records are present first.
4. Record the actual staging URL SiteGround returns. Do not guess its hostname,
   staging number, filesystem path or database name from the copy's label.

The tool has capacity limits and does not currently support WordPress Multisite;
see [SiteGround's staging creation guide](https://www.siteground.com/tutorials/staging/create-staging)
and [staging plan availability](https://www.siteground.com/technology).
If DNS is external and the staging URL fails, ask SiteGround which specific records
are required. An agent must show and obtain exact approval before any DNS changes.

## Deferred step 2. Protect and identify the clone before development

Inspect the clone's current controls first; the following are proposed staging
actions for the owner or an exact approved agent batch, not assumed completed:

- Apply password/access protection and discourage search indexing on staging.
  Verify the actual staging response/access behavior and noindex directive.
- Check copied forms, booking, email, analytics and third-party integrations. Disable
  or sandbox external side effects only on staging after reviewing the exact settings.
  Use synthetic data; do not submit a real patient's information in tests.
- Verify the clone has a separate database and wp-config identity. Do not paste
  database passwords or private records into chat or Git. Minimize copied clinical
  records and decide how to handle them before anyone else gets access.
- Confirm the active theme, parent/child relationship, PHP version and plugin list.
  Record a backup/restore method that targets ONLY staging.

Record current/proposed settings, affected staging URL, verification and rollback
in a local ignored review under `reports/`. Protection and noindex are settings
writes, so do not let the agent apply them without the required exact approval.

## Deferred step 3. Set up a dedicated SSH key

Windows OpenSSH `ssh` and `sftp` are available on this machine. Keep the private key
outside the repository. To generate a new key yourself, choose a NEW unused filename
and a passphrase; do not overwrite an existing key:

```powershell
ssh-keygen -t ed25519 -a 100 -f "$env:USERPROFILE/.ssh/sg_staging_seo" -C "seo-staging"
```

In **Site Tools > Devs > SSH Keys Manager > Import**, import only the `.pub` file.
Use the key's **Actions > SSH Credentials** to obtain the SSH host, username and
port. SiteGround documents SSH/SFTP port `18765`; use your displayed credentials.
Restrict allowed IP access where practical and revoke unused keys. See
[SiteGround's SSH/key guide](https://www.siteground.com/kb/what-is-ssh)
and [SSH credential instructions](https://www.siteground.com/kb/access-site-ssh-connection).

SiteGround warns that SSH keys have access to all files for a site and cannot be
limited to particular folders. A key named staging is not a server-enforced folder
restriction. For stronger isolation, use a separately provisioned staging site/account
when feasible. Avoid multisite-wide credentials for this project.

## Deferred step 4. Pin the SSH server identity

Obtain the server's SSH host-key fingerprint from a trusted SiteGround source or
support channel. Capture the advertised host key to a separate local known_hosts
file and compare its fingerprint BEFORE trusting it. `ssh-keyscan` alone does not
authenticate a server. Do not accept an unverified prompt, disable strict checking
or automatically replace a changed key. Keep the resulting file outside Git.

Load the passphrase-protected key into your local SSH agent yourself if desired.
Do not put a passphrase/private key in an environment variable, source or logs.
Connection settings below use file PATHS, not secret key contents.

## Deferred step 5. Set shell variables and verify paths read-only

Use `.env.staging.example` as a checklist. It is not automatically loaded. Set
concrete values in your PowerShell session, for example:

```powershell
$env:SG_STAGING_SFTP_HOST = 'HOST_FROM_SITE_TOOLS'
$env:SG_STAGING_USER = 'USER_FROM_SITE_TOOLS'
$env:SG_STAGING_PORT = '18765'
$env:SG_STAGING_SSH_KEY_PATH = "$env:USERPROFILE/.ssh/sg_staging_seo"
$env:SG_STAGING_KNOWN_HOSTS_PATH = "$env:USERPROFILE/.ssh/known_hosts_sg_staging"
$env:SG_STAGING_SITE_URL = 'https://ACTUAL_STAGING_HOST'
$env:SG_PRODUCTION_SITE_URL = 'https://meadowandmindpsychology.com/'
$env:SG_STAGING_WP_ROOT = '/ACTUAL/PHYSICAL/STAGING/WORDPRESS_ROOT'
$env:SG_PRODUCTION_WP_ROOT = '/ACTUAL/PHYSICAL/PRODUCTION/WORDPRESS_ROOT'
$env:SG_STAGING_THEME_SLUG = 'ACTUAL_CHILD_THEME_SLUG'
$env:SG_STAGING_THEME_DIR = "$($env:SG_STAGING_WP_ROOT)/wp-content/themes/$($env:SG_STAGING_THEME_SLUG)"
```

Uppercase strings are placeholders, not verified paths. The SSH server host may be
shared with production; it need not equal the staging website hostname. Confirm
installation separation and paths directly. Never target a theme path solely because
it contains the word staging.

After host-key verification, open a read-only SSH session:

```powershell
ssh -p $env:SG_STAGING_PORT -i $env:SG_STAGING_SSH_KEY_PATH `
  -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -o ForwardAgent=no `
  -o "UserKnownHostsFile=$env:SG_STAGING_KNOWN_HOSTS_PATH" `
  "$($env:SG_STAGING_USER)@$($env:SG_STAGING_SFTP_HOST)"
```

Run only inspection commands in that session: `pwd`, `ls`, `readlink -f` on the
actual roots/destination parents, `stat` and `sha256sum` on relevant files. Do not
write/install/activate anything. Verify roots are distinct and non-overlapping;
check symlinks and shared hard-linked files so staging edits cannot alter production.
Verify the separate DB/site identity without disclosing secrets. Reading WordPress
through WP-CLI may boot plugins with side effects; begin with filesystem inspection.

Download the necessary theme source read-only into ignored `deploy/baseline/` and
review it locally. Do not download wp-config, databases or clinical uploads into Git.
Record current file hashes and active theme evidence for the future review.

## Deferred step 6. Prepare a local release for remote staging

```powershell
Copy-Item deploy/staging.example.json deploy/staging.local.json
```

After local code review, fill the config's `files` list with explicit source-to-theme
file mappings. Keep `environment` at `staging` and `remote_writes_enabled` at `false`.
Run the local-only preparer:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_staging.py --config deploy/staging.local.json
```

Use local PHP matching the staging major/minor version when mapping PHP files;
the preparer refuses PHP files without `php -l`. PHP was not available during the
initial architecture setup. No PHP or schema implementation is included yet.

## Deferred step 7. Approve the exact batch, then activate transfer

Fill the generated `review.md` with actual current/proposed diffs, affected URLs,
clinician confirmations, validation, ancillary writes and staging-only rollback.
Have the owner approve the exact batch. The approval request must include backup
and restoration/removal actions if automatic rollback is intended.

`deploy/Upload-Staging.ps1.example` deliberately throws before any network activity.
Its checklist and commented SFTP command define the transport blueprint. Implement
that placeholder only after verifying the installation and first concrete release.
There is no current live uploader to enable with a flag.

The approved uploader must recheck targets/current hashes, back up replaced files,
upload only enumerated payload files, verify remote hashes and log partial progress.
Do not use a whole-repository/theme sync or recursive deletes. Re-run staging smoke
checks and code-mode structured-data tests; protected staging should remain private.
Never promote through SiteGround's live-deployment controls in this project.

## Local runtime setup

The audit dependencies are in `requirements.txt`; the release preparer itself uses
only the standard library (Python 3.12+). From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If venv creation cannot bootstrap pip, create it with `py -m venv --without-pip .venv`
and use a working global pip to install locally:

```powershell
py -m pip --python .venv install -r requirements.txt
```

Root `AGENTS.md` is the Codex project instruction hook; no additional `config.toml`
or SEO plugin is required. It routes tasks to `prompts/` while retaining audit and
approval rules. See [OpenAI's AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
