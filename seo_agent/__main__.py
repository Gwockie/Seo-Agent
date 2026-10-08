"""Read-only CLI and guarded local Streamlit launcher."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import SiteConfig, legacy_phrases
from .storage import Store, new_id

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / 'secrets'


def main():
    p = argparse.ArgumentParser(prog='seo_agent')
    p.add_argument('--workspace', type=Path, default=Path(os.environ.get('SEO_WORKSPACE', ROOT / 'workspace' / 'private')))
    p.add_argument('--secrets', type=Path, default=SECRETS, help='Explicit protected Desktop OAuth / legacy credential directory')
    sub = p.add_subparsers(dest='command', required=True)
    app = sub.add_parser('app', help='Launch the local loopback interface')
    app.add_argument('--demo', action='store_true')
    app.add_argument('--port', type=int, default=8501)
    auth = sub.add_parser('auth')
    auth.add_argument('--connection', help='Exact connection ID to reconnect; omitted creates an independent account')
    auth.add_argument('--reauth', action='store_true')
    auth.add_argument('--account')
    sites = sub.add_parser('sites')
    sites.add_argument('--connection')
    connection = sub.add_parser('add-connection', help='Create an independent account reference; no consent or token write')
    connection.add_argument('--label', required=True)
    selected = sub.add_parser('select-connection', help='Validate exact property access before selecting this site account')
    selected.add_argument('--site-id', required=True)
    selected.add_argument('--connection', required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--site')
    snap.add_argument('--url')
    snap.add_argument('--site-id', help='Configured site ID; preferred for multi-site audits')
    snap.add_argument('--connection')
    snap.add_argument('--days', type=int, default=90)
    snap.add_argument('--lag-days', type=int, default=3)
    snap.add_argument('--max-pages', type=int, default=200)
    snap.add_argument('--inspect', action='store_true')
    snap.add_argument('--inspect-limit', type=int, default=100)
    init = sub.add_parser('seed-original', help='Explicitly configure original practice; no inferred domain/facts')
    init.add_argument('--name', default='Meadow & Mind')
    init.add_argument('--url', required=True)
    init.add_argument('--site', required=True)
    init.add_argument('--connection')
    imported = sub.add_parser('import-profile')
    imported.add_argument('file', type=Path)
    imported.add_argument('--site-id')
    migrated = sub.add_parser('migrate-token')
    migrated.add_argument('--site-id', required=True)
    migrated.add_argument('--connection', required=True)
    legacy = sub.add_parser('register-legacy')
    legacy.add_argument('--site-id', required=True)
    legacy.add_argument('--data', type=Path, required=True)
    legacy.add_argument('--reports', type=Path, required=True)
    legacy.add_argument('--associate', action='store_true')
    backup_cmd = sub.add_parser('backup')
    backup_cmd.add_argument('destination', type=Path)
    restore_cmd = sub.add_parser('restore')
    restore_cmd.add_argument('archive', type=Path)
    restore_cmd.add_argument('new_workspace', type=Path)
    check = sub.add_parser('storage-check', help='Read-only protection diagnostic; creates no files')
    check.add_argument('--path', type=Path, help='Check another existing asset directory')
    sub.add_parser('setup-check', help='Read-only prerequisite summary; never refreshes or prints credentials')
    args = p.parse_args()
    if args.command == 'app':
        if not 1024 <= args.port <= 65535:
            p.error('Use an unprivileged port')
        workspace = ROOT / 'workspace' / 'demo' if args.demo else args.workspace
        env = {**os.environ, 'SEO_WORKSPACE': str(workspace.resolve()), 'SEO_DEMO': '1' if args.demo else '0'}
        return subprocess.call([sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'app.py'), '--server.address=127.0.0.1', f'--server.port={args.port}', '--server.enableCORS=true', '--server.enableXsrfProtection=true', '--browser.gatherUsageStats=false', '--server.headless=true'], cwd=ROOT, env=env)
    from .protection import require_protected, storage_status
    if args.command == 'storage-check':
        from .storage import private_location
        target = args.path if args.path is not None else private_location(args.workspace)
        result = storage_status(target)
        print(json.dumps(result, indent=2))
        return 0 if result['verified'] else 1
    if args.command == 'setup-check':
        from .preflight import setup_status
        print(json.dumps(setup_status(args.workspace, args.secrets, ROOT), indent=2))
        return 0  # A diagnostic, not a release/live-access certificate.
    if args.command == 'restore':
        from .backup import restore
        restore(args.archive, args.new_workspace)
        print('Workspace restored. Google connections are detached; reconnect explicitly on this machine.')
        return 0
    from .storage import credential_location
    secrets = credential_location(args.secrets)
    store = Store(args.workspace, enforce_protection=True)
    if args.command == 'add-connection':
        print(store.add_connection(args.label))
    elif args.command == 'select-connection':
        from .credentials import load_connection
        from .gsc import service_for_credentials, validate_access
        store.connection(args.connection)
        config = store.site(args.site_id)
        validate_access(service_for_credentials(load_connection(args.connection)), config.gsc_property, config.url)
        config.connection_id = args.connection
        store.save_site(config, args.site_id)
        print('Selected exact connection after read-only property validation: ' + args.connection)
    elif args.command == 'auth':
        from .credentials import authorize_connection
        from .storage import checked_id
        require_protected(store.root)
        require_protected(secrets)
        if args.reauth and not args.connection:
            p.error('--reauth requires the exact --connection ID; another account is never implicitly replaced')
        cid = checked_id(args.connection) if args.connection else new_id()
        if args.connection:
            store.connection(cid)
        authorize_connection(cid, secrets / 'client_secret.json', account=args.account)
        store.add_connection(args.account or 'Google connection', cid)
        # Only create default CLI pointer if there is no working selection or legacy token.
        pointer = secrets / 'connection.json'
        if not pointer.exists() and not (secrets / 'token.json').exists():
            pointer.write_text(json.dumps({'connection_id': cid}), encoding='utf-8')
        print('Authorized secure connection: ' + cid)
    elif args.command == 'sites':
        from .gsc import list_sites, service_for_credentials
        from .credentials import load_connection
        if args.connection:
            store.connection(args.connection)
            records = service_for_credentials(load_connection(args.connection)).sites().list().execute().get('siteEntry', [])
        else:
            require_protected(secrets)
            records = list_sites(secrets)
        if not records:
            print('No accessible properties. OAuth access does not grant property access.')
        for item in records:
            print(f"{item.get('siteUrl')}\t{item.get('permissionLevel')}")
    elif args.command == 'snapshot':
        from .runner import run_site, run_snapshot, run_lock, AuditContext, GLOBAL_LOCK
        from .gsc import services, service_for_credentials, validate_access
        from .credentials import load_connection
        settings = dict(days=args.days, lag_days=args.lag_days, max_pages=args.max_pages, inspect=args.inspect, inspect_limit=args.inspect_limit)
        if args.site_id:
            if args.site or args.url or args.connection:
                p.error('--site-id uses its own configuration; do not combine --site, --url or --connection')
            aid = run_site(store, args.site_id, progress=print, **settings)
            print('Audit: ' + aid)
        else:
            if not args.site or not args.url:
                p.error('Provide --site-id or both --site and --url')
            # Original CLI's historical output paths and original-site classification remain.
            config = SiteConfig(name='Legacy CLI practice', url=args.url, gsc_property=args.site, industry='psychology', location='Paoli', phrases=legacy_phrases(), service_groups={'adhd_assessment': ['ADHD assessment', 'ADHD testing', 'ADHD evaluation'], 'therapy': ['therapy', 'therapist'], 'psychological_testing': ['psychological testing']})
            require_protected(ROOT / 'data')
            require_protected(ROOT / 'reports')
            if args.connection:
                store.connection(args.connection)
                svc = service_for_credentials(load_connection(args.connection))
            else:
                require_protected(secrets)
                svc = services(secrets)
            validate_access(svc, args.site, args.url)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            ctx = AuditContext(new_id(), new_id(), config, ROOT / 'data' / stamp, ROOT / 'reports' / stamp, **settings)
            with run_lock(GLOBAL_LOCK):
                manifest, _ = run_snapshot(ctx, svc, progress=print)
            print(f"Snapshot {manifest['status']}: {ctx.data_dir}; {ctx.reports_dir / 'snapshot.md'}")
    elif args.command == 'seed-original':
        from .import_export import seed_original
        print(seed_original(store, name=args.name, url=args.url, property_url=args.site, connection_id=args.connection))
    elif args.command == 'import-profile':
        if args.file.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Profile exceeds 2 MiB')
        config = SiteConfig.model_validate_json(args.file.read_text(encoding='utf-8'))
        print(store.save_site(config, args.site_id))
    elif args.command == 'migrate-token':
        from .credentials import migrate_legacy
        require_protected(store.root)
        require_protected(secrets)
        store.connection(args.connection)
        config = store.site(args.site_id)
        migrate_legacy(secrets / 'token.json', args.connection, config)
        print('Token copied and verified. Legacy token retained. Explicitly select this connection in site setup.')
    elif args.command == 'register-legacy':
        from .import_export import register_legacy
        require_protected(store.root)
        require_protected(args.data)
        require_protected(args.reports)
        print(register_legacy(store, args.site_id, args.data, args.reports, associate=args.associate))
    elif args.command == 'backup':
        from .backup import backup
        backup(store, args.destination)
        print('Credential-free private backup created. Keep it on verified encrypted storage.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        from .protection import ProtectionError
        if isinstance(exc, ProtectionError):
            print('Setup required: ' + str(exc) + ' Run setup-check; see docs/setup-and-migration.md.', file=sys.stderr)
            sys.exit(1)
        # No raw OAuth/HTTP/import exception text enters terminal logs.
        print('Operation unavailable or rejected. Check setup, site/property association, protected storage, connection and bounded configuration. Existing credentials/evidence were preserved.', file=sys.stderr)
        sys.exit(1)
