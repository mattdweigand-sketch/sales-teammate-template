import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspaces/pipeline/scripts"))
from account_usage import resolve_org, summarize_usage


class AccountUsageTests(unittest.TestCase):
    def evidence(self):
        return {"Account": {"Admin_Organization_UUID__c": "org", "Org_UUID__c": "org"},
                "org_uuid": "org", "data_through": "2026-10-03", "billed_seats": 5,
                "rows": [{"user_email": "one@example.com", "window_queries": 10, "l7_queries": 1},
                         {"user_email": "two@example.com", "window_queries": "2", "l7_queries": 0},
                         {"user_email": "idle@example.com", "window_queries": None, "l7_queries": None}]}

    def test_counts_do_not_conflate_billing_roster_and_activity(self):
        result = summarize_usage(self.evidence())
        self.assertEqual([result[key] for key in ("billed_seats", "roster_seats", "active_users", "active_last_seven_days")],
                         [5, 3, 2, 1])

    def test_unknown_billing_is_not_zero(self):
        evidence = self.evidence()
        del evidence["billed_seats"]
        self.assertIsNone(summarize_usage(evidence)["billed_seats"])

    def test_org_fallback_and_conflict(self):
        self.assertEqual(resolve_org({"Org_UUID__c": "org"}), "org")
        with self.assertRaisesRegex(ValueError, "org ids differ.*one.*two"):
            resolve_org({"Admin_Organization_UUID__c": "one", "Org_UUID__c": "two"})
        with self.assertRaisesRegex(ValueError, "org id missing"):
            resolve_org({})

    def test_usage_org_must_match_salesforce(self):
        evidence = self.evidence()
        evidence["org_uuid"] = "other"
        with self.assertRaisesRegex(ValueError, "does not match"):
            summarize_usage(evidence)

    def test_duplicate_roster_rows_are_not_double_counted(self):
        evidence = self.evidence()
        evidence["rows"].append({**evidence["rows"][0], "user_email": "ONE@example.com"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize_usage(evidence)

    def test_missing_activity_field_is_unknown_not_zero(self):
        evidence = self.evidence()
        del evidence["rows"][0]["window_queries"]
        with self.assertRaisesRegex(ValueError, "activity fields missing"):
            summarize_usage(evidence)

    def test_invalid_counts_fail_closed(self):
        for invalid in (True, -1, "NaN", "Infinity", "invalid"):
            with self.subTest(invalid=invalid):
                evidence = self.evidence()
                evidence["rows"][0]["window_queries"] = invalid
                with self.assertRaises(ValueError):
                    summarize_usage(evidence)
        evidence = self.evidence()
        evidence["billed_seats"] = "2.5"
        with self.assertRaisesRegex(ValueError, "whole number"):
            summarize_usage(evidence)


if __name__ == "__main__":
    unittest.main()
