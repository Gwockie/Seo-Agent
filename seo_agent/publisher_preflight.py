"""Inert checks of asserted inventory against the pinned Elementor certificate.

Passing this check is never runtime certification, isolation review or authority.
In particular, no engine or table identity is inferred from a server default.
"""
from .elementor_publishing import ADAPTER, adapter_hash, contract_manifest


def inspect_inventory(data, *, phase="setup"):
    if phase not in {"setup", "installed"}:
        raise ValueError("Unknown publisher preflight phase")
    manifest = contract_manifest()
    software = data.get("software", [])
    missing, conflicts = [], []
    for kind in ("core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"):
        if kind not in data.get("complete_inventory", []):
            missing.append(f"Complete {kind} inventory")

    def require(kind, name, version, sha=None, *, active=False, optional=False):
        rows = [s for s in software if s["kind"] == kind and (name is None or s["name"] == name)]
        label = f"{kind} {name or 'runtime'}"
        if not rows and optional:
            return
        if len(rows) != 1:
            missing.append(f"One explicit {label} inventory row")
            return
        row = rows[0]
        if not row.get("version"):
            missing.append(f"{label} version")
        elif row["version"] != version:
            conflicts.append(f"{label} version {row['version']} differs from pinned {version}.")
        if sha:
            if not row.get("sha256"):
                missing.append(f"{label} source hash")
            elif row["sha256"] != sha:
                conflicts.append(f"{label} source hash differs from the pinned certificate.")
        if active and row.get("active") is not True:
            missing.append(f"Confirmed active {label}")

    require("core", "WordPress", manifest["wordpress"], manifest["core_includes_php"])
    require("php", None, manifest["php_runtime"])
    require("database", None, manifest["database_runtime"])
    require("theme", manifest["theme"], manifest["theme_version"], manifest["theme_files"], active=True)
    require("plugin", "elementor/elementor.php", manifest["elementor"], manifest["elementor_files"], active=True)
    companion = "local-seo-publisher/local-seo-publisher.php"
    require("plugin", companion, "0.2.0", adapter_hash(), active=phase == "installed", optional=phase == "setup")
    for row in software:
        kind, name = row["kind"], row["name"]
        if kind in {"mu_plugin", "dropin"}:
            conflicts.append(f"Recorded {kind} {name} is excluded by {ADAPTER}, including when active status is unknown.")
        elif kind in {"theme", "plugin"}:
            allowed = {manifest["theme"]} if kind == "theme" else {"elementor/elementor.php", companion}
            if name not in allowed:
                if row.get("active") is True:
                    conflicts.append(f"Active {kind} {name} is outside the pinned Elementor certificate.")
                elif row.get("active") is not False:
                    missing.append(f"Active status of {kind} {name}")

    tables = [s for s in software if s["kind"] == "table_engine"]
    for role in ("posts", "postmeta", "options", "journal"):
        rows = [s for s in tables if s.get("table_role") == role]
        if not rows and role == "journal" and phase == "setup":
            continue  # Its exact creation is disclosed in the separate setup packet.
        if len(rows) != 1:
            missing.append(f"One authoritative {role} table identity and engine")
            continue
        row = rows[0]
        if sum(s["name"] == row["name"] for s in tables) != 1:
            conflicts.append(f"Table {row['name']} has ambiguous role or engine evidence.")
        if not row.get("version"):
            missing.append(f"{role} table {row['name']} engine")
        elif row["version"] != "InnoDB":
            conflicts.append(f"{role} table {row['name']} uses {row['version']}; {ADAPTER} requires InnoDB "
                             "for atomic content, mirror and journal writes. A server default or another table cannot substitute.")
    return {"adapter": ADAPTER, "phase": phase, "certainty": "administrator_asserted",
            "missing": list(dict.fromkeys(missing)), "conflicts": list(dict.fromkeys(conflicts)),
            "publishing_compatible": False,
            "note": "This compares current asserted inventory only. Fresh certified endpoint checks, host effects, staging validation and exact approvals remain required. Do not alter production to fit this certificate."}
