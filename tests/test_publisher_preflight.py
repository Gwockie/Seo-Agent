import copy
import unittest

from seo_agent import elementor_publishing as ep
from seo_agent.publisher_preflight import inspect_inventory


def certified_inventory(*, installed=False):
    m = ep.contract_manifest()
    rows = [dict(kind=k, name=n, version=v, sha256=h, active=True) for k, n, v, h in (
        ("core", "WordPress", m["wordpress"], m["core_includes_php"]),
        ("php", "PHP", m["php_runtime"], ""),
        ("database", "MariaDB", m["database_runtime"], ""),
        ("theme", m["theme"], m["theme_version"], m["theme_files"]),
        ("plugin", "elementor/elementor.php", m["elementor"], m["elementor_files"]))]
    roles = ["posts", "postmeta", "options"]
    if installed:
        roles.append("journal")
        rows.append(dict(kind="plugin", name="local-seo-publisher/local-seo-publisher.php",
                         version="0.2.0", sha256=ep.adapter_hash(), active=True))
    rows.extend(dict(kind="table_engine", name="synthetic_" + ("lseo_operations" if r == "journal" else r),
                     table_role=r, version="InnoDB") for r in roles)
    return dict(software=rows, complete_inventory=["core", "php", "database", "table_engine",
                                                  "theme", "plugin", "mu_plugin", "dropin"])


class InventoryPreflightTests(unittest.TestCase):
    def test_setup_and_installed_are_distinct_and_never_certify(self):
        data = certified_inventory()
        setup = inspect_inventory(data)
        self.assertEqual(setup["missing"] + setup["conflicts"], [])
        self.assertFalse(setup["publishing_compatible"])
        installed = inspect_inventory(data, phase="installed")
        self.assertTrue(any("journal" in x for x in installed["missing"]))
        self.assertTrue(any("local-seo-publisher" in x for x in installed["missing"]))
        installed = inspect_inventory(certified_inventory(installed=True), phase="installed")
        self.assertEqual(installed["missing"] + installed["conflicts"], [])
        self.assertFalse(installed["publishing_compatible"])

    def test_complete_labels_cannot_replace_missing_rows_or_roles(self):
        data = certified_inventory()
        data["software"] = [dict(kind="table_engine", name="default engine", version="InnoDB")]
        report = inspect_inventory(data)
        for word in ("WordPress", "PHP", "database", "elementor", "posts", "postmeta", "options"):
            self.assertTrue(any(word.casefold() in x.casefold() for x in report["missing"]), word)
        data = certified_inventory()
        for row in data["software"]:
            row.pop("table_role", None)
        self.assertTrue(any("posts table" in x for x in inspect_inventory(data)["missing"]))

    def test_nontransactional_role_cannot_be_hidden_by_other_prefix_or_default(self):
        data = certified_inventory(installed=True)
        for role in ("posts", "postmeta", "options", "journal"):
            value = copy.deepcopy(data)
            row = next(s for s in value["software"] if s.get("table_role") == role)
            row["version"] = "MyISAM"
            value["software"].extend([dict(kind="table_engine", name="other_" + role, version="InnoDB"),
                                      dict(kind="table_engine", name="server default", version="InnoDB")])
            report = inspect_inventory(value, phase="installed")
            self.assertTrue(any(role + " table" in x and "MyISAM" in x for x in report["conflicts"]))
        data["software"].append(dict(kind="table_engine", name="another_posts", table_role="posts", version="InnoDB"))
        self.assertTrue(any("posts table" in x for x in inspect_inventory(data)["missing"]))

    def test_wrong_versions_hashes_and_unknown_active_inventory_block(self):
        for field, value in (("version", "unsupported"), ("sha256", "f" * 64), ("active", None)):
            data = certified_inventory()
            next(s for s in data["software"] if s["kind"] == "plugin")[field] = value
            report = inspect_inventory(data)
            self.assertTrue(report["missing"] + report["conflicts"])
        for kind in ("mu_plugin", "dropin"):
            for active in (True, False, None):
                data = certified_inventory()
                data["software"].append(dict(kind=kind, name="synthetic-cache.php", active=active))
                self.assertTrue(inspect_inventory(data)["conflicts"])
        for active in (True, None):
            data = certified_inventory()
            data["software"].append(dict(kind="plugin", name="extra/plugin.php", active=active))
            report = inspect_inventory(data)
            self.assertTrue(report["missing"] + report["conflicts"])

    def test_existing_wrong_companion_is_not_tolerated_before_setup(self):
        data = certified_inventory(installed=True)
        next(s for s in data["software"] if s["name"] == "local-seo-publisher/local-seo-publisher.php")["sha256"] = "f" * 64
        self.assertTrue(inspect_inventory(data)["conflicts"])
        with self.assertRaises(ValueError):
            inspect_inventory(data, phase="unknown")

    def test_partial_authenticated_facts_cannot_be_overridden_by_assertions(self):
        data = certified_inventory(installed=True)
        cases = [dict(kind="plugin", name="extra/cache.php", active=True),
                 dict(kind="theme", name="another-theme", active=True),
                 dict(kind="plugin", name="elementor/elementor.php", version="unsupported", active=True),
                 dict(kind="plugin", name="elementor/elementor.php", active=False)]
        for row in cases:
            with self.subTest(row=row):
                report = inspect_inventory(data, authenticated={"software": [row]})
                self.assertTrue(any("Authenticated REST" in x for x in report["conflicts"]))
        # Omitted rows/unknown values prove neither absence nor disagreement.
        for rows in ([], [dict(kind="plugin", name="elementor/elementor.php", version="", active=None)],
                     [dict(kind="plugin", name="unused/cache.php", active=False)]):
            self.assertEqual(inspect_inventory(data, authenticated={"software": rows})["conflicts"], [])
        report = inspect_inventory({}, authenticated={"software": data["software"]})
        self.assertTrue(report["missing"])
