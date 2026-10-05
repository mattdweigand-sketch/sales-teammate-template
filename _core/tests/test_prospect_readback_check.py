import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
sys.path.insert(0, str(SCRIPTS))
import prospect_readback_check


class ReadbackTests(unittest.TestCase):
    def test_exact_gmail_fields_with_provider_metadata(self):
        proposal = {"to": "jane@example.com", "subject": "Question", "body": "Hello\n\nOperator"}
        self.assertEqual("match", prospect_readback_check.compare(proposal, {**proposal, "id": "draft-1"})["verdict"])

    def test_changed_recipient_subject_or_complete_body(self):
        proposal = {"to": "jane@example.com", "subject": "Question", "body": "Hello\n\nOperator"}
        for field in proposal:
            with self.subTest(field=field):
                actual = {**proposal, field: proposal[field] + " changed"}
                self.assertEqual([field], prospect_readback_check.compare(proposal, actual)["fields"])

    def test_missing_null_and_type_changes_are_not_matches(self):
        self.assertEqual("mismatch", prospect_readback_check.compare({"WhoId": None}, {})["verdict"])
        self.assertEqual("mismatch", prospect_readback_check.compare({"Enabled": True}, {"Enabled": 1})["verdict"])
        self.assertEqual("mismatch", prospect_readback_check.compare({"ActivityDate": "2026-09-30"}, {"ActivityDate": None})["verdict"])

    def test_nested_fields_and_order(self):
        self.assertEqual("mismatch", prospect_readback_check.compare({"record": {"Id": "001"}}, {"record": {"Id": "001", "type": "Account"}})["verdict"])
        self.assertEqual("mismatch", prospect_readback_check.compare({"to": ["a", "b"]}, {"to": ["b", "a"]})["verdict"])

    def test_empty_proposal_cannot_pass(self):
        with self.assertRaises(ValueError):
            prospect_readback_check.compare({}, {"Id": "001"})

    def test_gmail_rejects_added_copy_recipients_and_incomplete_proposal(self):
        proposal = {"to": "jane@example.com", "subject": "Question", "body": "Hello"}
        self.assertEqual("match", prospect_readback_check.compare(proposal, {**proposal, "id": "d1", "cc": []}, gmail=True)["verdict"])
        for field in ("cc", "bcc", "CC", "Bcc"):
            for value in (["extra@example.com"], "extra@example.com", None):
                self.assertEqual("mismatch", prospect_readback_check.compare(proposal, {**proposal, field: value}, gmail=True)["verdict"])
        with self.assertRaises(ValueError):
            prospect_readback_check.compare({"to": "jane@example.com"}, proposal, gmail=True)

    def test_cli_match_mismatch_and_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "expected.json"
            actual = Path(directory) / "actual.json"
            expected.write_text(json.dumps({"WhoId": "003A"}))
            for contents, code, verdict in [('{"WhoId":"003A"}', 0, "match"),
                                            ('{}', 1, "mismatch"),
                                            ('{"WhoId":NaN}', 2, "error")]:
                actual.write_text(contents)
                result = subprocess.run([sys.executable, str(SCRIPTS / "prospect_readback_check.py"),
                                         "--expected", str(expected), "--actual", str(actual)],
                                        capture_output=True, text=True)
                self.assertEqual(code, result.returncode, result.stderr)
                self.assertEqual(verdict, json.loads(result.stdout)["verdict"])


if __name__ == "__main__":
    unittest.main()
