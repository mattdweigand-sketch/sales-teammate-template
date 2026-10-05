"""Digest of saved search_email outputs: recipient handling, ordering, input tolerance."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "scripts"))
import gmail_thread_digest as digest  # noqa: E402


class ThreadDigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def save(self, payload) -> str:
        self.counter += 1
        path = self.root / f"output_{self.counter}.json"
        path.write_text(json.dumps({"result": payload}))
        return str(path)

    def run_digest(self, *argv: str) -> str:
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            digest.main(list(argv))
        return out.getvalue()

    def test_string_to_is_not_character_split(self) -> None:
        path = self.save({"email_results": {"emails": [{
            "date": "2026-09-20T10:00:00Z", "from_": "rep@seller.example", "to": "buyer@example.com",
            "subject": "Pilot", "body": "<p>Hello</p>",
        }]}})
        out = self.run_digest(path)
        self.assertIn("| to buyer@example.com\n", out)
        self.assertIn("  Hello\n", out)
        self.assertIn("1 emails", out)

    def test_mixed_date_formats_sort_newest_first(self) -> None:
        path = self.save({"email_results": {"emails": [
            {"date": "2026-09-19T10:00:00+00:00", "from_": "a", "to": [], "subject": "older-iso"},
            {"date": "Mon, 21 Sep 2026 10:00:00 -0700", "from_": "b", "to": [], "subject": "newest-rfc"},
            {"date": "2026-09-20T10:00:00Z", "from_": "c", "to": [], "subject": "middle-iso"},
            {"date": None, "from_": "d", "to": [], "subject": "undated"},
        ]}})
        lines = self.run_digest(path).splitlines()[:-1]   # three lines per block, then the count
        subjects = [lines[i + 1].strip() for i in range(0, len(lines), 3)]
        self.assertEqual(subjects, ["newest-rfc", "middle-iso", "older-iso", "undated"])

    def test_failed_or_unread_results_do_not_claim_zero_emails(self) -> None:
        listed = self.save([{"not": "a dict"}])
        garbage = self.save("not json")
        for path in (listed, garbage, self.save({"error":"timeout"})):
            with self.assertRaises(ValueError):
                self.run_digest(path)
        self.assertIn("0 emails",self.run_digest(self.save({"email_results":{"emails":[]}})))

    def test_attachment_filter_skips_inline_image_names(self) -> None:
        path = self.save({"email_results": {"emails": [{
            "date": "2026-09-20T10:00:00Z", "from_": "a", "to": ["b"], "subject": "Docs", "body": "See attached",
            "attachments": [{"filename": "image001.png"}, {"filename": "ATT00001.htm"}, {"filename": "Order Form.pdf"}],
        }]}})
        out = self.run_digest(path, "--chars", "5")
        self.assertIn("  attachments: Order Form.pdf\n", out)
        self.assertIn("  See a [truncated, 7 more chars]\n", out)

    def test_cut_body_is_marked_and_message_id_is_printed(self) -> None:
        """A buyer's timing statement past the cut is not silently lost; the id lets the reader fetch the full body."""
        filler = "Thanks for the walkthrough. " * 12
        path = self.save({"email_results": {"emails": [{
            "email_id": "m-long", "thread_id": "t-long", "date": "2026-09-20T10:00:00Z", "from_": "buyer@example.com",
            "to": ["rep@seller.example"], "subject": "Re: order form",
            "body": filler + "We cannot sign this quarter.",
        }]}})
        out = self.run_digest(path)
        self.assertIn("| id m-long thread t-long |", out)
        self.assertNotIn("cannot sign", out)
        self.assertRegex(out, r"\[truncated, \d+ more chars\]")
        self.assertIn("cannot sign", self.run_digest(path, "--chars", "400"))


    def test_pagination_requires_every_page_with_matching_cursor(self):
        first=self.save({"email_results":{"emails":[],"next_cursor":"p2"}})
        with self.assertRaisesRegex(ValueError,"pagination"):
            self.run_digest(first)
        second=self.save({"email_results":{"emails":[]}})
        Path(first).with_name(Path(first).name.replace("output_","input_")).write_text(json.dumps({"arguments":{"queries":["from:@example.com"]}}))
        Path(second).with_name(Path(second).name.replace("output_","input_")).write_text(json.dumps({"arguments":{"queries":["from:@example.com"],"cursor":"p2"}}))
        self.assertIn("0 emails",self.run_digest(first,second))

if __name__ == "__main__":
    unittest.main()
