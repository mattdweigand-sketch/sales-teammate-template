"""Run from the repo root: python3 -m unittest discover -s _core/tests"""
import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
sys.path.insert(0, str(SCRIPTS))
import prospect_common  # noqa: E402

POLICY = prospect_common.load_policy(CORE)
PACIFIC = ZoneInfo("America/Los_Angeles")


class FixedDatetime(datetime):
    """datetime whose now() is 2026-09-24 04:00 UTC, which is 2026-09-23 21:00 Pacific."""
    INSTANT = datetime(2026, 9, 24, 4, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.INSTANT.astimezone(tz) if tz else cls.INSTANT.replace(tzinfo=None)


def write_core(d, policy_text, icp_text=None):
    (d / "policy.yaml").write_text(policy_text)
    if icp_text is not None:
        (d / "icp.md").write_text(icp_text)


class LoadersTests(unittest.TestCase):
    def test_core_resolves_to_repo_core_dir(self):
        self.assertEqual(prospect_common.CORE, CORE)

    def test_load_policy_reads_identity(self):
        self.assertEqual(POLICY["identity"]["timezone"], "America/Los_Angeles")
        self.assertTrue(POLICY["identity"]["sfdc_user_id"].startswith("005"))

    def test_load_policy_missing_dir_raises_oserror(self):
        with self.assertRaises(OSError):
            prospect_common.load_policy(Path("/nonexistent"))

    def test_markdown_frontmatter_keeps_dashes_inside_values(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            write_core(d, "identity: {}\n", "---\nterritory:\n  note: 'a --- b'\n  min_employees: 200\n---\n# ICP\n\n---\n\nBody rule with --- inside.\n")
            fm = prospect_common.markdown_document(d / "icp.md")["meta"]
        self.assertEqual(fm["territory"]["note"], "a --- b")
        self.assertEqual(fm["territory"]["min_employees"], 200)

    def test_markdown_document_without_block_raises(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            write_core(d, "identity: {}\n", "# ICP\nno frontmatter here\n")
            with self.assertRaises(ValueError):
                prospect_common.markdown_document(d / "icp.md")["meta"]

    def test_load_taxonomy_and_entry_lookup(self):
        tax = prospect_common.load_taxonomy(CORE)
        entry, tier = prospect_common.taxonomy_entry(tax, "public_ai_initiative")
        self.assertEqual((entry["id"], tier), ("public_ai_initiative", "tier1"))
        entry, tier = prospect_common.taxonomy_entry(tax, "exec_ai_statements")
        self.assertEqual(tier, "tier2")
        self.assertEqual(prospect_common.taxonomy_entry(tax, "generic_ai_marketing"), (None, None))
        self.assertEqual(prospect_common.taxonomy_entry(tax, "vibes"), (None, None))

    def test_taxonomy_types_covers_every_tier(self):
        tax = prospect_common.load_taxonomy(CORE)
        types = prospect_common.taxonomy_types(tax)
        self.assertEqual(len(types), sum(len(v) for v in tax["tiers"].values()))
        self.assertEqual(types["generic_ai_marketing"]["tier"], "tier3")
        self.assertEqual(types["paid_individuals_present"]["source"], "warehouse")
        self.assertIsNone(types["ai_exec_appointment"]["source"])
        self.assertEqual(types["ai_exec_appointment"]["freshness_days"], 90)


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()

    def tearDown(self):
        if self.old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.old_tz
        time.tzset()

    def test_policy_tz(self):
        self.assertEqual(str(prospect_common.policy_tz(POLICY)), "America/Los_Angeles")

    def test_policy_today_is_pacific_not_system_date(self):
        self.assertEqual(FixedDatetime.now(timezone.utc).date(), date(2026, 9, 24))   # the system UTC date
        with mock.patch.object(prospect_common, "datetime", FixedDatetime):
            self.assertEqual(prospect_common.policy_today(POLICY), date(2026, 9, 23))         # the policy date
            now = prospect_common.policy_now(POLICY)
        self.assertEqual(now.utcoffset(), datetime(2026, 9, 23, 21, tzinfo=PACIFIC).utcoffset())
        self.assertEqual(now, FixedDatetime.INSTANT)

    def test_policy_now_is_aware(self):
        self.assertIsNotNone(prospect_common.policy_now(POLICY).tzinfo)


class ParseIsoTests(unittest.TestCase):
    def test_z_suffix(self):
        self.assertEqual(prospect_common.parse_iso("2026-09-21T14:00:00Z"),
                         datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc))

    def test_offset(self):
        got = prospect_common.parse_iso("2026-09-21T14:00:00-07:00")
        self.assertEqual(got, datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc))

    def test_naive_is_none(self):
        self.assertIsNone(prospect_common.parse_iso("2026-09-21T14:00:00"))
        self.assertIsNone(prospect_common.parse_iso("2026-09-21T14:00:00", POLICY))

    def test_bare_date_without_policy_is_none(self):
        self.assertIsNone(prospect_common.parse_iso("2026-09-21"))

    def test_bare_date_with_policy_is_noon_in_policy_tz(self):
        got = prospect_common.parse_iso("2026-09-21", POLICY)
        self.assertEqual(got, datetime(2026, 9, 21, 12, 0, tzinfo=PACIFIC))
        self.assertEqual(got.utcoffset(), datetime(2026, 9, 21, tzinfo=PACIFIC).utcoffset())

    def test_garbage_and_empty_are_none(self):
        for bad in ("", None, "yesterday", "2026-13-01", 20260921):
            self.assertIsNone(prospect_common.parse_iso(bad), bad)


if __name__ == "__main__":
    unittest.main()
