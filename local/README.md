# Local WordPress workspace (not installed yet)

The active plan is to retain StartUp, audit read-only and prepare local source.
See `docs/LOCAL_DEVELOPMENT.md` before setting up a WordPress test copy.

Future local-only directories:

```text
local/wordpress/   WordPress runtime and inspected theme/plugin files
local/runtime/     Local environment configuration
local/backups/     Sanitized exports and local recovery files
```

Everything under `local/` except this README is ignored. Deployable reviewed source
belongs under `src/`. Never connect the local copy to the production database or
live email/form/booking integrations. Minimize sensitive data and use synthetic tests.
No WordPress runtime, database export or hosting connection is created by this scaffold.
