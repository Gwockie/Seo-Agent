"""Build a local-only review package. No SSH, SFTP, HTTP, or remote write code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SUFFIXES = {".php", ".json", ".js", ".css", ".html"}
COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
ENV_REF = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(text: str):
    def reject_constant(value):
        raise ValueError(f"Non-standard JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)


def value(config: dict, key: str, environ: dict) -> str:
    result = config.get(key)
    if not isinstance(result, str):
        raise ValueError(f"Missing string setting: {key}")
    match = ENV_REF.fullmatch(result)
    if match:
        result = environ.get(match[1], "")
    if not result or result != result.strip() or any(c in result for c in "\r\n\x00${}"):
        raise ValueError(f"Set a concrete value for {key}; environment variable is missing or invalid")
    return result


def safe_path(text: str, *, absolute: bool = False) -> PurePosixPath:
    if not isinstance(text, str) or text.startswith("/") != absolute:
        raise ValueError("Expected an absolute POSIX path" if absolute else "Expected a relative POSIX path")
    parts = text[1:].split("/") if absolute else text.split("/")
    if not parts or any(not COMPONENT.fullmatch(p) or p in {".", ".."} for p in parts):
        raise ValueError(f"Unsafe path: {text!r}")
    return PurePosixPath(text)


def site_url(text: str) -> str:
    url = urlsplit(text)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.port not in {None, 443}):
        raise ValueError("Site URLs must be HTTPS without credentials, query or fragment")
    return url.hostname.lower().removeprefix("www.")


def target_settings(config: dict, environ: dict) -> dict:
    if (type(config.get("schema_version")) is not int or config["schema_version"] != 1
            or config.get("environment") != "staging"
            or config.get("remote_writes_enabled") is not False):
        raise ValueError("Require schema_version=1, environment=staging and remote_writes_enabled=false")
    settings = {k: value(config, k, environ) for k in (
        "staging_site_url", "production_site_url", "staging_wp_root",
        "production_wp_root", "theme_slug", "theme_dir")}
    if site_url(settings["staging_site_url"]) == site_url(settings["production_site_url"]):
        raise ValueError("Staging and production must have distinct hostnames")
    staging = safe_path(settings["staging_wp_root"], absolute=True)
    production = safe_path(settings["production_wp_root"], absolute=True)
    if staging == production or staging in production.parents or production in staging.parents:
        raise ValueError("Staging and production roots must not overlap")
    slug = settings["theme_slug"]
    if not COMPONENT.fullmatch(slug) or slug in {".", ".."}:
        raise ValueError("Unsafe theme slug")
    theme_dir = safe_path(settings["theme_dir"], absolute=True)
    if theme_dir != staging / "wp-content" / "themes" / slug:
        raise ValueError("Theme directory must match the explicitly declared staging installation and slug")
    return settings


def mapped_files(config: dict, root: Path) -> list[tuple[dict, bytes]]:
    files = config.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Add an explicit nonempty files map after reviewing actual theme source")
    records = []
    targets = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"source", "target"}:
            raise ValueError("Each file map must contain only source and target")
        source_rel = safe_path(item["source"])
        target_rel = safe_path(item["target"])
        if source_rel.parts[0] != "src" or len(source_rel.parts) < 2:
            raise ValueError("Only explicit src/ files may enter a release")
        if (source_rel.suffix not in ALLOWED_SUFFIXES
                or target_rel.suffix != source_rel.suffix):
            raise ValueError("Require matching PHP, JSON, JS, CSS or HTML file suffixes")
        key = target_rel.as_posix().casefold()
        if any(key == t or key.startswith(t + "/") or t.startswith(key + "/") for t in targets):
            raise ValueError("Duplicate or colliding deployment targets")
        targets.add(key)
        source = root.joinpath(*source_rel.parts)
        if any(p.is_symlink() or p.is_junction() for p in [source, *source.parents] if p != root.parent):
            raise ValueError("Local source symlinks/junctions are not permitted")
        if not source.resolve().is_relative_to((root / "src").resolve()) or not source.is_file():
            raise ValueError("Source must be an existing file inside src/")
        content = source.read_bytes()
        check = "Manual syntax and functional validation required"
        if source.suffix == ".json":
            strict_json(content.decode("utf-8-sig"))
            check = "Strict JSON parse passed; semantic/structured-data checks still required"
        elif source.suffix == ".php":
            php = shutil.which("php")
            if not php:
                raise ValueError("PHP is required to prepare mapped PHP files; install a matching local PHP runtime")
            result = subprocess.run([php, "-l", str(source)], capture_output=True, timeout=30)
            if result.returncode:
                raise ValueError(f"PHP syntax check failed for {source_rel}")
            # Hash the checked file, refusing a concurrent edit during lint.
            if source.read_bytes() != content:
                raise ValueError("Source changed during validation; prepare a new release")
            check = "php -l passed; staging integration and runtime checks still required"
        records.append(({"source": source_rel.as_posix(), "target": target_rel.as_posix(),
                         "sha256": digest(content), "bytes": len(content), "local_check": check,
                         "current_remote_state": "UNKNOWN: requires read-only inspection"}, content))
    return records


def prepare(config_path: Path, root: Path = ROOT, environ: dict | None = None) -> Path:
    config = strict_json(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    settings = target_settings(config, os.environ if environ is None else environ)
    records = mapped_files(config, root)
    release = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = root / "dist" / "staging" / release
    if not output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release directory escaped the repository")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "release": release, "environment": "staging",
                "remote_writes_enabled": False, "approval_status": "PENDING HUMAN REVIEW",
                "target": settings, "files": [record for record, _ in records]}
    for record, content in records:
        payload = output / "payload" / record["target"]
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(content)
    serialized = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(serialized)
    (output / "manifest.sha256").write_text(digest(serialized) + "\n", encoding="utf-8")
    rows = [f"| {r['source']} | {settings['theme_dir']}/{r['target']} | UNKNOWN | {r['sha256']} |"
            for r, _ in records]
    review = f"""# Staging release {release} — pending human approval

Staging URL: {settings['staging_site_url']}
Theme directory: {settings['theme_dir']}
Manifest SHA-256: {digest(serialized)}

| Local source | Affected absolute staging file | Current bytes/hash | Proposed SHA-256 |
| --- | --- | --- | --- |
{chr(10).join(rows)}

For EVERY file attach the actual current text/diff or verified absence and proposed
text/diff. Identify affected page URLs/settings, the exact intended action and
clinical facts requiring confirmation. Hashes alone do not explain behavior.

- [ ] Verify SSH host key, physical paths, destination parents and isolated staging DB.
- [ ] Verify current remote hashes/absence and active theme before writing.
- [ ] Attach code review, PHP/JS/CSS/schema tests and staging validation plan.
- [ ] Enumerate ALL ancillary writes (directories, temporary files, includes, settings).
- [ ] Verify a staging-only backup and document exact rollback writes and hashes.
- [ ] Present this exact batch to the human; record their explicit approval locally.

Unknown current values, unconfirmed facts or changed payloads block transfer.
This package does not grant approval. The transfer placeholder remains disabled.
Rollback also requires explicit approval of its exact writes; production is prohibited.
"""
    (output / "review.md").write_text(review, encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "deploy" / "staging.local.json")
    args = parser.parse_args()
    try:
        output = prepare(args.config)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"Local preparation stopped: {exc}\n")
    print(f"Local review package: {output}\nNo remote connection or writes performed.")


if __name__ == "__main__":
    main()
