import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "workspaces/pipeline/workflows/pilot-usage/scripts"
sys.path.insert(0, str(SCRIPTS))
from resolve_pilot import resolve_pilot

AS_OF = "2026-10-04T10:00:00-07:00"


class PilotResolveTests(unittest.TestCase):
    def record(self, identifier="pilot"):
        return {"Id": identifier, "AccountId": "account", "OwnerId": "operator", "IsClosed": False, "IsWon": False,
                "Deal_Type__c": "Paid Trial", "Trial_Expiration_Date__c": "2026-10-04",
                "Account": {"Name": "Customer", "Admin_Organization_UUID__c": "org", "Org_UUID__c": "org"}}

    def resolve(self, records, **selector):
        return resolve_pilot(records, "operator", AS_OF, **(selector or {"opportunity_id": "pilot"}))

    def test_paid_closed_won_expiring_today_is_eligible_by_id(self):
        record = self.record()
        record.update(IsClosed=True, IsWon=True)
        self.assertEqual(self.resolve([record])["opportunity"]["Id"], "pilot")

    def test_resolve_reference_requires_records_array_not_query_response(self):
        reference = (SCRIPTS.parent / "references/resolve.md").read_text()
        self.assertIn("`--input` takes only the saved records list (a JSON array), not the full query response", reference)
        self.assertIn("records from all completed pages", reference)
        with self.assertRaisesRegex(ValueError, "input must be a complete Salesforce record list"):
            self.resolve({"records": [self.record()], "done": True})

    def test_paid_closed_won_future_end_is_eligible(self):
        record = self.record()
        record.update(IsClosed=True, IsWon=True, Trial_Expiration_Date__c="2026-11-01")
        self.assertEqual(self.resolve([record])["org_uuid"], "org")

    def test_expired_pilot_is_rejected_open_or_closed_won(self):
        for closed in (False, True):
            record = self.record()
            record.update(IsClosed=closed, IsWon=closed, Trial_Expiration_Date__c="2026-10-03")
            with self.subTest(closed=closed), self.assertRaisesRegex(ValueError, "no eligible pilot"):
                self.resolve([record])

    def test_multiple_pilots_ask_but_explicit_id_selects(self):
        records = [self.record(), self.record("second")]
        with self.assertRaisesRegex(ValueError, "multiple eligible pilots"):
            self.resolve(records, account_id="account")
        self.assertEqual(self.resolve(records, opportunity_id="second")["opportunity"]["Id"], "second")

    def test_mismatched_org_stops_even_with_explicit_id(self):
        record = self.record()
        record["Account"]["Org_UUID__c"] = "wrong"
        with self.assertRaisesRegex(ValueError, "org ids differ"):
            self.resolve([record])

    def test_missing_org_does_not_guess_by_name(self):
        record = self.record()
        record["Account"] = {"Name": "Customer"}
        with self.assertRaisesRegex(ValueError, "org id missing"):
            self.resolve([record])

    def test_unowned_closed_lost_and_nonpaid_won_are_ineligible(self):
        changes = ({"OwnerId": "other"}, {"IsClosed": True, "IsWon": False},
                   {"IsClosed": True, "IsWon": True, "Deal_Type__c": "Annual"},
                   {"IsClosed": True, "IsWon": True, "Trial_Expiration_Date__c": None})
        for change in changes:
            record = self.record()
            record.update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "no eligible pilot"):
                self.resolve([record])

    def test_open_nonpaid_pilot_and_undated_paid_trial_remain_supported(self):
        for change in ({"Deal_Type__c": "Unpaid"}, {"Trial_Expiration_Date__c": None}):
            record = self.record()
            record.update(change)
            self.assertEqual(self.resolve([record])["opportunity"]["Id"], "pilot")

    def test_expired_record_does_not_make_account_ambiguous(self):
        expired = self.record("old")
        expired["Trial_Expiration_Date__c"] = "2026-09-01"
        self.assertEqual(self.resolve([expired, self.record()], account_name="Customer")["opportunity"]["Id"], "pilot")

    def test_offset_required_and_pacific_date_boundary(self):
        with self.assertRaisesRegex(ValueError, "offset"):
            resolve_pilot([self.record()], "operator", "2026-10-04T10:00:00", opportunity_id="pilot")
        record = self.record()
        record.update(IsClosed=True, IsWon=True, Trial_Expiration_Date__c="2026-10-03")
        result = resolve_pilot([record], "operator", "2026-10-04T01:00:00+00:00", opportunity_id="pilot")
        self.assertEqual(result["today"], "2026-10-03")

    def test_cli_returns_exit_two_for_ambiguity_and_zero_for_explicit_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            path.write_text(json.dumps([self.record(), self.record("second")]))
            command = [sys.executable, str(SCRIPTS / "resolve_pilot.py"), "--input", str(path),
                       "--owner-id", "operator", "--as-of", AS_OF]
            ambiguous = subprocess.run(command + ["--account-id", "account"], capture_output=True, text=True)
            self.assertEqual(ambiguous.returncode, 2)
            self.assertIs(json.loads(ambiguous.stdout)["valid"], False)
            selected = subprocess.run(command + ["--opportunity-id", "second"], capture_output=True, text=True)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(json.loads(selected.stdout)["opportunity"]["Id"], "second")


if __name__ == "__main__":
    unittest.main()
