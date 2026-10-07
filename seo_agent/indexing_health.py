"""Bounded, read-only checks of ordinary Google index records; no recovery writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

BASE = "https://meadowandmindpsychology.com/"
TARGETS = [BASE + p for p in (
    "individual-therapy/", "affordable-therapy-pennsylvania/",
    "psychological-assessments-paoli/",
)]
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
IMAGE = "{http://www.google.com/schemas/sitemap-image/1.1}"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_record(url: str, response: dict) -> dict:
    idx = response.get("inspectionResult", {}).get("indexStatusResult", {})
    reasons = []
    canonical = idx.get("googleCanonical")
    crawl = idx.get("lastCrawlTime")
    if idx.get("verdict") != "PASS":
        reasons.append("Google does not report a valid indexed URL")
    if canonical != url:
        reasons.append("Google canonical differs or is unavailable")
    if idx.get("userCanonical") != url:
        reasons.append("User canonical differs or is unavailable")
    if not crawl:
        reasons.append("No ordinary recorded crawl is reported")
    else:
        try:
            parsed_crawl = datetime.fromisoformat(crawl.replace("Z", "+00:00"))
            if parsed_crawl.tzinfo is None or parsed_crawl > datetime.now(timezone.utc):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            reasons.append("Ordinary crawl timestamp is invalid or future-dated")
    if idx.get("pageFetchState") != "SUCCESSFUL":
        reasons.append("Ordinary recorded fetch is not successful or unavailable")
    if idx.get("robotsTxtState") != "ALLOWED":
        reasons.append("Ordinary recorded robots permission is not allowed or unavailable")
    if idx.get("indexingState") != "INDEXING_ALLOWED":
        reasons.append("Ordinary recorded indexing permission is not allowed or unavailable")
    coverage = idx.get("coverageState", "")
    if not idx:
        stage = "missing_evidence"
    elif canonical and canonical != url:
        stage = "canonical_conflict"
    elif not reasons:
        stage = "indexed_preferred"
    elif "unknown" in coverage.lower():
        stage = "unknown"
    elif not crawl and "discovered" in coverage.lower():
        stage = "discovered_uncrawled"
    elif crawl and idx.get("verdict") != "PASS":
        stage = "crawled_excluded"
    else:
        stage = "incomplete_or_blocked"
    return {
        "url": url, "healthy": not reasons, "stage": stage,
        "coverage_state": coverage, "last_crawl_utc": crawl,
        "google_canonical": canonical, "user_canonical": idx.get("userCanonical"),
        "reasons": reasons,
    }


def sitemap_contract(folder: Path, required: list[str], previous: dict | None = None) -> dict:
    """Validate acquired XML locally. This function does not fetch or prove freshness."""
    errors, relations, hashes, entries = [], [], {}, []
    index_path = folder / "sitemap_index.xml"
    try:
        root = ET.fromstring(index_path.read_bytes())
        if root.tag != NS + "sitemapindex":
            raise ValueError("Index is not a sitemapindex in the sitemap 0.9 namespace")
        hashes[index_path.name] = hashlib.sha256(index_path.read_bytes()).hexdigest()
        children = []
        for item in root.findall(NS + "sitemap"):
            locs = item.findall(NS + "loc")
            if len(locs) != 1 or not (locs[0].text or "").strip():
                raise ValueError("Index entry requires exactly one location")
            children.append(locs[0].text.strip())
        if not children or len(children) > 20 or len(set(children)) != len(children):
            raise ValueError("Child set is empty, duplicated or exceeds bounded limit 20")
        for child in sorted(children):
            parts = urlsplit(child)
            if parts.scheme != "https" or parts.netloc != urlsplit(BASE).netloc:
                raise ValueError("Child has an unexpected host or scheme")
            if parts.query or parts.fragment or not re.fullmatch(r"/[A-Za-z0-9_-][A-Za-z0-9._-]*\.xml", parts.path):
                raise ValueError("Child does not map to a root-level local XML filename")
            file = folder / parts.path.lstrip("/")
            if file.resolve().parent != folder.resolve():
                raise ValueError("Child XML resolves outside the supplied sitemap directory")
            data = file.read_bytes()
            hashes[file.name] = hashlib.sha256(data).hexdigest()
            doc = ET.fromstring(data)
            if doc.tag != NS + "urlset":
                raise ValueError("Child is not a urlset; HTML challenges and nested indexes fail")
            relations.append(["child", BASE + "sitemap_index.xml", child])
            for item in doc.findall(NS + "url"):
                locs = item.findall(NS + "loc")
                if len(locs) != 1 or not (locs[0].text or "").strip():
                    raise ValueError("URL entry requires exactly one location")
                url = locs[0].text.strip()
                parsed = urlsplit(url)
                if parsed.scheme != "https" or parsed.netloc != urlsplit(BASE).netloc or parsed.fragment:
                    raise ValueError("Primary entry has an unexpected host, scheme or fragment")
                entries.append(url)
                relations.append(["entry", child, url])
                for image in item.findall(IMAGE + "image"):
                    images = image.findall(IMAGE + "loc")
                    if len(images) != 1 or not (images[0].text or "").strip():
                        raise ValueError("Image requires exactly one location")
                    relations.append(["image", url, images[0].text.strip()])
        if len(set(entries)) != len(entries):
            errors.append("Duplicate primary URLs across the acquired hierarchy")
        errors += ["Required landing missing from sitemap: " + url for url in required if url not in entries]
    except (ET.ParseError, OSError, ValueError) as exc:
        # Only locally generated errors/filenames are printed, not remote bodies.
        errors.append(str(exc))
    encoded = json.dumps(sorted(relations), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if previous and previous.get("relations_sha256") != digest:
        errors.append("Sitemap URL/child/image relationships changed; whole-manifest review is required")
    return {
        "healthy": not errors, "errors": errors, "relations_sha256": digest,
        "source_hashes": hashes, "primary_count": len(entries), "relations": sorted(relations),
        "freshness": "Local supplied evidence only; no current transport or index-policy verification",
    }


def evaluate_snapshot(records: list[dict], targets: list[str], previous: dict | None = None) -> dict:
    by_url = {r["url"]: r for r in records}
    old = {p["url"]: p for p in (previous or {}).get("pages", [])}
    pages = []
    for url in targets:
        record = by_url.get(url, {})
        page = evaluate_record(url, record.get("response", {}))
        page["retrieved_utc"] = record.get("retrieved_utc")
        page["regression"] = bool(old.get(url, {}).get("healthy") and not page["healthy"])
        pages.append(page)
    return {"healthy": all(p["healthy"] for p in pages), "pages": pages}


def collect_live(root: Path, site: str, targets: list[str]) -> tuple[list[dict], dict]:
    # Do not initiate new consent/re-authentication from a health check.
    token = root / "secrets" / "token.json"
    if not token.is_file():
        raise ValueError("Existing read-only token required; this check will not start authentication")
    saved = json.loads(token.read_text(encoding="utf-8"))
    if set(saved.get("scopes", [])) != {SCOPE}:
        raise ValueError("Existing token must have exactly the webmasters.readonly scope")
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(str(token), [SCOPE])
    if not creds.valid and not (creds.expired and creds.refresh_token):
        raise ValueError("Existing credentials unavailable; no new consent is initiated")
    from .gsc import services
    svc = services(root / "secrets")
    accessible = svc.sites().list().execute().get("siteEntry", [])
    if not any(s.get("siteUrl") == site for s in accessible):
        raise ValueError("Exact requested property is not accessible")
    records = []
    for url in targets:
        response = svc.urlInspection().index().inspect(body={
            "inspectionUrl": url, "siteUrl": site, "languageCode": "en-US",
        }).execute()
        records.append({"url": url, "retrieved_utc": now(), "response": response})
    submitted = svc.sitemaps().list(siteUrl=site).execute()
    submitted_utc = now()
    children = svc.sitemaps().list(siteUrl=site, sitemapIndex=site + "sitemap_index.xml").execute()
    metadata = {"submitted_retrieved_utc": submitted_utc, "response": submitted,
                "children_retrieved_utc": now(), "children_response": children}
    return records, metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="One bounded read of stored Google index records")
    source.add_argument("--replay", type=Path, help="Existing raw inspection array; never labelled fresh")
    parser.add_argument("--site", default=BASE)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--url", action="append", help="Exact critical preferred URL; default two services and assessment control")
    parser.add_argument("--previous", type=Path, help="Earlier health.json for regression comparison")
    parser.add_argument("--sitemap-dir", type=Path, help="Locally acquired complete XML hierarchy; no HTTP crawling")
    parser.add_argument("--out", type=Path, required=True, help="New local evidence directory (must not exist)")
    args = parser.parse_args(argv)
    targets = list(dict.fromkeys(args.url or TARGETS))
    if args.site != BASE or not 1 <= len(targets) <= 20 or any(not u.startswith(BASE) for u in targets):
        parser.error("Use the exact practice property and 1–20 URLs within its preferred prefix")
    if args.out.exists():
        parser.error("Output exists; evidence is append-only. Choose a new directory")
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    if previous and (previous.get("site") != args.site or previous.get("targets") != targets):
        parser.error("Previous evidence must have the same exact property and target set")
    if args.live:
        records, metadata = collect_live(args.root, args.site, targets)
    else:
        records = json.loads(args.replay.read_text(encoding="utf-8"))
        metadata = None
    result = evaluate_snapshot(records, targets, previous)
    result.update(site=args.site, targets=targets, evaluated_utc=now(),
                  evidence_mode="fresh_readonly_api" if args.live else "historical_replay")
    if args.sitemap_dir:
        result["sitemap"] = sitemap_contract(args.sitemap_dir, targets, (previous or {}).get("sitemap"))
        result["healthy"] = result["healthy"] and result["sitemap"]["healthy"]
    args.out.mkdir(parents=True)
    for name, data in (("inspection-raw.json", records), ("health.json", result), ("sitemaps-raw.json", metadata)):
        if data is not None:
            (args.out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Critical landing indexing health", "", "Evidence: " + result["evidence_mode"],
             "", "Result: " + ("PASS" if result["healthy"] else "FAIL — recovery not confirmed or regression detected"), ""]
    for page in result["pages"]:
        lines += [f"- {page['url']}: {page['stage']}; ordinary crawl {page['last_crawl_utc'] or 'unavailable'}; regression {page['regression']}."]
    lines += ["", "An API read reports Google's stored index state. It does not request crawling, run a live test, guarantee future indexing or schedule monitoring."]
    (args.out / "health.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("PASS" if result["healthy"] else "FAIL: critical landing indexing health")
    for page in result["pages"]:
        print(page["url"], page["stage"], "REGRESSION" if page["regression"] else "")
    print("Evidence:", args.out)
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("Health check failed:", str(exc))
        raise SystemExit(2)
    except Exception as exc:
        # Avoid printing HTTP/OAuth bodies or credentials.
        print("Health check unavailable:", type(exc).__name__)
        raise SystemExit(2)
