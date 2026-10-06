"""Static account adoption SQL contracts. No warehouse is touched. Native Snowflake syntax and schemas remain unverified.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
QUERIES = {
    "adoption_lookup.sql": ROOT / "workspaces/prospecting/workflows/signal-prospecting/01-research/scripts/adoption_lookup.sql",
}


def split(sql):
    header = [l for l in sql.splitlines() if l.startswith("--")]
    body = "\n".join(l.split("--")[0] for l in sql.splitlines() if not l.startswith("--"))
    return "\n".join(header), re.sub(r"'[^']*'", "''", body)   # string literals hold regex ? marks


class SqlContracts(unittest.TestCase):
    def test_header_bindings_match_placeholders(self):
        for name in QUERIES:
            header, body = split(QUERIES[name].read_text())
            declared = {int(n) for n in re.findall(r"\?(\d)", header)}
            self.assertEqual(declared, set(range(1, len(declared) + 1)), name)
            self.assertEqual(body.count("?"), len(declared), name)

    def test_adoption_lookup_lists_never_null(self):
        sql = QUERIES["adoption_lookup.sql"].read_text()
        for col in ("org_service_types", "org_platforms"):
            self.assertRegex(sql, rf"COALESCE\(\(SELECT LISTAGG\(DISTINCT \w+, ','\) FROM org_sub\), ''\)\s+AS {col}")

    def test_adoption_lookup_counts_only_live_orgs(self):
        sql = QUERIES["adoption_lookup.sql"].read_text()
        org_map = sql.split("org_map AS (")[1].split("),")[0]
        self.assertIn("o.is_deleted = FALSE", org_map)



if __name__ == "__main__":
    unittest.main()
