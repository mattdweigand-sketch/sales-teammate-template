"""Policy keys and reference frontmatter are consumed by something. Settings nobody reads are deleted, not kept."""
import re
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspaces/prospecting/scripts"))
import prospect_common  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
POLICY_REF = re.compile(r"(?<![A-Za-z0-9_])policy\.((?!yaml\b)[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)")


def skill_read_keys():
    """Dotted policy keys the stage contracts, their references and the SQL headers use."""
    from test_prospect_stage_contracts import stage_sources
    keys = set()
    for f in stage_sources() + sorted((ROOT / "workspaces/prospecting").rglob("scripts/*.sql")):
        keys.update(key.removeprefix("prospecting.") for key in POLICY_REF.findall(f.read_text()))
    return keys


def read_in_one_script(top, key):
    """A script subscripts policy[top][key] directly, or assigns name = ...[top] and then reads name[key] or name.get(key)."""
    scripts = list((ROOT / "workspaces/prospecting").rglob("scripts/*.py"))
    top, key = re.escape(top), re.escape(key)
    for p in scripts:
        code = p.read_text()
        if re.search(r'\["' + top + r'"\]\s*\["' + key + r'"\]', code):
            return True
        for alias in re.findall(r'^\s*(\w+)\s*=\s*[^=\n]*\["' + top + r'"\]\s*$', code, re.M):
            if re.search(r'\b' + alias + r'(?:\["|\.get\(")' + key + r'"', code):
                return True
    return False


class PolicyPathTests(unittest.TestCase):
    def test_internal_domains_have_one_canonical_home_and_no_identity_alias(self):
        text = (CORE / "policy.yaml").read_text()
        policy = yaml.safe_load(text)
        self.assertEqual(re.findall(r"^\s*internal_domains:", text, re.M), ["  internal_domains:"])
        self.assertEqual(policy["tooling"]["internal_domains"], ["seller.example", "seller-tools.example"])
        self.assertIn(
            "  internal_domains: [seller.example, seller-tools.example]   # never a buyer; excluded from attendee, inbox, roster, and contact-stat reads\n",
            text,
        )
        self.assertNotIn("internal_domains", policy["prospecting"]["identity"])
        self.assertNotIn("internal_domains", prospect_common.load_policy(CORE)["identity"])
        fixture = yaml.safe_load((CORE / "tests/prospecting-fixtures/policy.yaml").read_text())
        self.assertNotIn("internal_domains", fixture["identity"])

    def test_no_maintained_consumer_cites_the_retired_identity_domain_key(self):
        retired = "prospecting.identity" + ".internal_domains"
        files = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTEXT.md"]
        files += [path for folder in (CORE, ROOT / "workspaces") for path in folder.rglob("*")
                  if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".sql"}]
        self.assertEqual([str(path.relative_to(ROOT)) for path in files if retired in path.read_text()], [])
        adoption = ROOT / "workspaces/prospecting/workflows/research/references/adoption.md"
        self.assertIn("Stop when it is in `policy.tooling.internal_domains`", adoption.read_text())
        self.assertIn("Internal domains are never adoption targets", adoption.read_text())

    def test_no_orphan_policy_keys(self):
        """Every second-level policy key is read by one script (that script also reads its top-level block) or is
        referenced as policy.<top>.<key> by a stage document or SQL header, itself or through a dotted child."""
        pol = prospect_common.load_policy(CORE)
        listed = skill_read_keys()
        self.assertTrue(listed, "no stage document references a policy key, test is stale")
        orphans = []
        for top, block in pol.items():
            if not isinstance(block, dict):
                continue
            for key in block:
                dotted = f"{top}.{key}"
                covered = dotted in listed or any(k.startswith(dotted + ".") for k in listed)
                if not (read_in_one_script(top, key) or covered):
                    orphans.append(dotted)
        self.assertEqual(orphans, [], f"policy keys no script reads and no stage document references: {orphans}")

    def test_reference_headers_hold_only_consumed_settings(self):
        tax = prospect_common.load_taxonomy(CORE)
        self.assertEqual(set(tax), {"tiers"})
        ids = []
        for tier, entries in tax["tiers"].items():
            for entry in entries:
                ids.append(entry["id"])
                self.assertTrue(set(entry) <= {"id", "freshness_days", "source"})
                if tier != "tier3":
                    self.assertGreater(entry["freshness_days"], 0)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
