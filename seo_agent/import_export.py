"""Bounded, explicitly site-associated imports and spreadsheet-safe exports."""
from __future__ import annotations
import csv
import io
import json
import re
import zipfile
from pathlib import Path

import pandas as pd

from .config import Phrase, SiteConfig, public_url, legacy_phrases
from .storage import Store, historical_date

MAX_IMPORT = 2 * 1024 * 1024
PHRASE_FIELDS = ["site_id", "phrase", "group", "related_terms", "location", "priority", "landing_page", "active"]
DATA_FILES = {"manifest.json", "gsc_sitemaps.json", "reviewed-page-observations.json", "crawl.csv", "opportunities.csv", "url_inspection.csv", "gsc_window.csv", *{"gsc_" + n + ".csv" for n in ("totals", "query_page", "queries", "pages", "daily", "device", "country")}}


def backup_evidence_path(relative, kind):
    """Allow known evidence formats, including inert historical page captures."""
    parts = relative.parts
    if len(parts) not in (1, 2) or any(v in relative.name.casefold() for v in ("token", "secret", "credential")) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", relative.name):
        return False
    if kind == "reports":
        return len(parts) == 1 and relative.suffix == ".md"
    if kind != "data":
        return False
    if len(parts) == 2:
        return (parts[0] == "comparison" and relative.name in DATA_FILES) or (parts[0] == "pages" and relative.suffix in {".html", ".txt"})
    return relative.name in DATA_FILES | {"validation.json", "robots.txt"} or relative.suffix in {".html", ".txt", ".xml"}


def spreadsheet_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def spreadsheet_frame(df):
    safe = df.map(spreadsheet_safe)
    safe.columns = [spreadsheet_safe(str(c)) for c in df.columns]
    return safe


def safe_csv(df):
    return spreadsheet_frame(df).to_csv(index=False).encode("utf-8-sig")


def export_phrases(sid, config):
    rows = [{"site_id": sid, **p.model_dump(), "related_terms": json.dumps(p.related_terms)} for p in config.phrases]
    return safe_csv(pd.DataFrame(rows, columns=PHRASE_FIELDS))


def import_phrases(raw: bytes, sid, config, *, associate=False):
    if len(raw) > MAX_IMPORT:
        raise ValueError("Phrase import exceeds 2 MiB")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        fields = set(reader.fieldnames or [])
        if fields - set(PHRASE_FIELDS) or not {"phrase", "group"}.issubset(fields):
            raise ValueError("Unexpected phrase columns")
        if "site_id" not in fields and not associate:
            raise ValueError("Unscoped CSV requires explicit selected-site association")
        phrases = []
        for row in reader:
            if len(phrases) >= 500 or None in row:
                raise ValueError("Import row/column limit exceeded")
            if "site_id" in fields and row["site_id"] != sid:
                raise ValueError("CSV belongs to another site or has ambiguous association")
            values = {k: v for k, v in row.items() if k != "site_id" and v not in (None, "")}
            # Escape prefixes added by our own spreadsheet-safe export are data.
            for k in ("phrase", "group", "location", "landing_page"):
                if k in values and values[k].startswith("'") and values[k][1:].lstrip().startswith(("=", "+", "-", "@")):
                    values[k] = values[k][1:]
            if "priority" in values:
                values["priority"] = int(values["priority"])
            if "active" in values:
                if values["active"].lower() not in ("true", "false"):
                    raise ValueError("Active must be True or False")
                values["active"] = values["active"].lower() == "true"
            if "related_terms" in values:
                values["related_terms"] = json.loads(values["related_terms"])
            phrases.append(Phrase.model_validate(values))
        candidate = {**config.model_dump(), "phrases": [p.model_dump() for p in phrases]}
        return SiteConfig.model_validate(candidate)
    except (UnicodeError, csv.Error, TypeError, OverflowError):
        raise ValueError("Invalid phrase CSV") from None


def register_legacy(store, sid, data_path, reports_path, *, associate=False):
    store.require_private_write()
    data, reports = Path(data_path).resolve(), Path(reports_path).resolve()
    # Validate locations before reading any imported manifest.
    if not data.is_relative_to(store.legacy_root / "data") or not reports.is_relative_to(store.legacy_root / "reports"):
        raise ValueError("Historical folders must be under the legacy data/reports roots")
    if data.parent != store.legacy_root / "data" or reports.parent != store.legacy_root / "reports" or data.name != reports.name:
        raise ValueError("Historical data/reports must be the matching snapshot pair")
    if store.enforce_protection:
        from .protection import require_protected
        require_protected(data)
        require_protected(reports)
    config = store.site(sid)
    path = data / "manifest.json"
    if not path.resolve().is_relative_to(data) or not path.exists() or path.stat().st_size > MAX_IMPORT:
        raise ValueError("Historical manifest is missing or oversized")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError("Historical manifest is invalid") from None
    for key in ("url", "site_url"):
        if manifest.get(key) and public_url(manifest[key]) != config.url:
            raise ValueError("Historical public URL differs from selected site")
    source_url = manifest.get("url") or manifest.get("site_url")
    prop = manifest.get("site")
    if prop and prop != config.gsc_property:
        raise ValueError("Historical exact property differs from selected site")
    if not source_url or not prop:
        if not associate:
            raise ValueError("Ambiguous/public-only import requires explicit site association")
    created = manifest.get("created_utc")
    time_source = "manifest.created_utc"
    if not created:
        # Old public captures record a date and a UTC stamp in the folder name.
        # Preserve its source and never substitute the current import date.
        stamp = re.fullmatch(r"(?:public-)?(\d{8}T\d{6}Z)", data.name)
        if not stamp:
            raise ValueError("Historical collection timestamp is missing; a UTC snapshot folder name is required")
        created = stamp.group(1)
        time_source = "snapshot folder UTC name; exact time was not recorded in the manifest"
    created = historical_date(created)
    if manifest.get("collected_date") and manifest["collected_date"] != created[:10]:
        raise ValueError("Historical collection date conflicts with its UTC timestamp")
    for old in store.audits(sid):
        if Path(old["data_path"]) == data:
            return old["id"]
    aid = store.create_audit(sid, legacy_paths=(data, reports), created=created)
    # Metadata only; never write to original files or pretend narrative is automated.
    with store.db() as db:
        unknown_rules = {"registry_version": "unknown", "industry": config.industry, "profile_version": "unknown", "rules": {}, "note": "Original rule versions and configuration were not recorded. Current selected profile is an association for viewing, not historical provenance."}
        db.execute("UPDATE audits SET manifest=?, resolved=?, status=? WHERE id=? AND site_id=?", (json.dumps({"legacy": True, "source": manifest, "gsc_available": bool(prop), "collection_time_source": time_source, "note": "Historical rules/configuration unknown; imported narrative is human-authored. Selected profile is an association only."}), json.dumps(unknown_rules), "legacy" if prop else "legacy-public-only", aid, sid))
    return aid


def seed_original(store, *, name, url, property_url, connection_id=None):
    """Requires explicit original identity; seed known goals, not clinical facts."""
    config = SiteConfig(name=name, url=url, gsc_property=property_url, connection_id=connection_id,
        industry="psychology", location="Paoli", brand_aliases=[name], phrases=legacy_phrases(),
        service_groups={"adhd_assessment": ["ADHD assessment", "ADHD testing", "ADHD evaluation"], "therapy": ["therapy", "therapist"], "psychological_testing": ["psychological testing"]})
    sid = store.save_site(config)
    store.add_change(sid, date="2026-10-06", action="User reported indexing fixes; exact actions and affected URLs were not supplied.", verification="user-reported; unverified", evidence="Implementation handoff dated 2026-10-07; fresh read-only inspection needed.")
    return sid


def report_packet(store, sid, aid):
    """Selected audit only. Raw CSV evidence stays local; exported CSV is escaped."""
    store.audit(sid, aid)
    buffer = io.BytesIO()
    total_size = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for kind in ("data", "reports"):
            sample = store.audit_file(sid, aid, kind, "manifest.json" if kind == "data" else "snapshot.md")
            for path in sorted(sample.parent.rglob("*")):
                if path.suffix not in (".csv", ".md", ".json") or not path.is_file():
                    continue
                if (kind == "data" and path.name not in DATA_FILES) or (kind == "reports" and path.suffix != ".md"):
                    continue
                relative = path.relative_to(sample.parent)
                if len(relative.parts) > 2 or (len(relative.parts) == 2 and (kind != "data" or relative.parts[0] != "comparison")):
                    raise ValueError("Unexpected evidence subtree")
                checked = store.audit_file(sid, aid, kind, path.name, period="previous" if len(relative.parts) == 2 else "current")
                if checked.stat().st_size > 40 * 1024 * 1024:
                    raise ValueError("Report packet file exceeds size limit")
                total_size += checked.stat().st_size
                if total_size > 100 * 1024 * 1024:
                    raise ValueError("Report packet exceeds export size limit")
                content = safe_csv(pd.read_csv(checked).fillna("")) if checked.suffix == ".csv" and checked.stat().st_size > 1 else checked.read_bytes()
                archive.writestr(kind + "/" + relative.as_posix(), content)
    return buffer.getvalue()
