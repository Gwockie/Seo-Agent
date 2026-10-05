from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .auth import get_credentials
from .crawl import crawl
from .gsc import list_sites, export_performance, list_sitemaps, inspect_urls
from .analysis import build_opportunities, write_markdown_summary

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"

def main():
    p = argparse.ArgumentParser(prog="seo_agent")
    sub = p.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth")
    auth.add_argument("--reauth", action="store_true", help="Authorize again to switch accounts; replace the token only after consent succeeds")
    auth.add_argument("--account", help="Suggest this Google account in the browser login screen")
    sub.add_parser("sites")

    s = sub.add_parser("snapshot")
    s.add_argument("--site", required=True, help='Exact GSC property, e.g. sc-domain:example.com')
    s.add_argument("--url", required=True, help="Public website root URL")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--lag-days", type=int, default=3)
    s.add_argument("--max-pages", type=int, default=200)
    s.add_argument("--inspect", action="store_true", help="Run URL Inspection for crawled 200-status pages")
    s.add_argument("--inspect-limit", type=int, default=100)

    args = p.parse_args()
    if args.command == "snapshot" and (args.days < 1 or args.lag_days < 0 or args.max_pages < 1 or args.inspect_limit < 1):
        p.error("days, max-pages, and inspect-limit must be positive; lag-days must be nonnegative")

    if args.command == "auth":
        get_credentials(SECRETS, reauth=args.reauth, account=args.account)
        print("Authorization complete. Token saved to secrets/token.json")
        return

    if args.command == "sites":
        sites = list_sites(SECRETS)
        if not sites:
            print("No Search Console properties are accessible to the authorized Google account. "
                  "Check that account's access in Search Console. OAuth test-user access does not grant property access.")
            return
        for item in sites:
            print(f"{item.get('siteUrl')}\t{item.get('permissionLevel')}")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_dir = ROOT / "data" / stamp
    reports_dir = ROOT / "reports" / stamp
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("Pulling Search Console performance...")
    gsc_meta = export_performance(SECRETS, args.site, data_dir, args.days, args.lag_days)

    print("Listing submitted sitemaps...")
    sitemaps = list_sitemaps(SECRETS, args.site)
    (data_dir / "gsc_sitemaps.json").write_text(json.dumps(sitemaps, indent=2), encoding="utf-8")

    print("Crawling public site...")
    crawl_df = crawl(args.url, data_dir / "crawl.csv", max_pages=args.max_pages)

    opp = build_opportunities(data_dir)
    opp.to_csv(data_dir / "opportunities.csv", index=False)

    if args.inspect and not crawl_df.empty and "status" in crawl_df:
        urls = crawl_df.loc[crawl_df["status"].astype(str).eq("200"), "final_url"].dropna().tolist()
        print(f"Inspecting up to {args.inspect_limit} URLs in Google's index...")
        inspect_urls(SECRETS, args.site, urls, data_dir / "url_inspection.csv", limit=args.inspect_limit)

    write_markdown_summary(data_dir, reports_dir)

    manifest = {
        "created_utc": stamp,
        "site": args.site,
        "url": args.url,
        "gsc": gsc_meta,
        "max_pages": args.max_pages,
        "url_inspection_enabled": bool(args.inspect),
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nSnapshot complete:\n  data: {data_dir}\n  report: {reports_dir / 'snapshot.md'}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Avoid dumping HTTP/OAuth response bodies that may contain sensitive data.
        from googleapiclient.errors import HttpError
        if isinstance(exc, HttpError):
            print(f"Error: Google API returned HTTP {exc.resp.status}. Check account/property access, API enablement, and quota.", file=sys.stderr)
        elif isinstance(exc, (ValueError, FileNotFoundError)):
            print(f"Error: {exc}", file=sys.stderr)
        else:
            print(f"Error: {type(exc).__name__}. Check connectivity and credential format; snapshot may be incomplete.", file=sys.stderr)
        sys.exit(1)
