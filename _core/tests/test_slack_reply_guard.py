"""Shared Slack collection routes and positive triage auto-move vetoes."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspaces/pipeline/scripts"))
import gmail_contact_stats as stats
import yaml


class SlackReplyGuard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.as_of = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        self.sent = self.as_of - timedelta(days=1)
        self.contact = "buyer@example.com"
        self.path = self.root / "receipts.json"

    def receipt(self, **overrides):
        result = {
            "contact_email": self.contact,
            "ts": str(self.as_of.timestamp()),
            "permalink": "https://example.com/message",
            "verified_identity": True,
            "substantive": True,
            "is_bot": False,
        }
        result.update(overrides)
        return result

    def load(self, receipts):
        self.path.write_text(json.dumps(receipts))
        return stats.load_slack_replies(self.path, self.as_of, 14)

    def test_substantive_slack_reply_disqualifies_automatic_move(self):
        reply = self.load([self.receipt()])[self.contact]
        self.assertTrue(stats.slack_reply_blocks_auto_move(self.sent, reply))

    def test_equal_timestamp_blocks_and_earlier_reply_does_not(self):
        for difference, expected in ((0, True), (-1, False)):
            reply = self.load([self.receipt(ts=str(self.sent.timestamp() + difference))])[self.contact]
            self.assertEqual(stats.slack_reply_blocks_auto_move(self.sent, reply), expected)

    def test_only_verified_substantive_nonbot_replies_count(self):
        for field, value in (("verified_identity", False), ("substantive", False), ("is_bot", True)):
            self.assertEqual(self.load([self.receipt(**{field: value})]), {})

    def test_latest_contact_reply_wins_regardless_of_receipt_order(self):
        old = self.receipt(ts=str(self.sent.timestamp()), contact_email=self.contact.upper())
        self.assertEqual(self.load([self.receipt(), old])[self.contact], self.as_of)

    def test_other_contact_never_vetoes_this_contact(self):
        replies = self.load([self.receipt(contact_email="other@example.com")])
        self.assertFalse(stats.slack_reply_blocks_auto_move(self.sent, replies.get(self.contact)))

    def test_configured_lookback_bounds_receipts(self):
        boundary = self.as_of - timedelta(days=14)
        self.assertIn(self.contact, self.load([self.receipt(ts=str(boundary.timestamp()))]))
        self.assertEqual(self.load([self.receipt(ts=str(boundary.timestamp() - 1))]), {})

    def test_invalid_or_future_timestamps_require_review(self):
        for timestamp in (None, True, "NaN", "inf", "invalid", -1, self.as_of.timestamp() + 1):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.load([self.receipt(ts=timestamp)])

    def test_reply_after_collection_is_accepted_only_by_fresh_recheck_and_vetoes_move(self):
        reply_time = self.as_of + timedelta(minutes=5)
        recheck_time = self.as_of + timedelta(minutes=10)
        self.path.write_text(json.dumps([self.receipt(ts=str(reply_time.timestamp()))]))
        with self.assertRaisesRegex(ValueError, "Slack reply is later than as-of, review required"):
            stats.load_slack_replies(self.path, self.as_of, 14)
        replies = stats.load_slack_replies(self.path, recheck_time, 14)
        self.assertEqual(replies[self.contact], reply_time)
        self.assertTrue(stats.slack_reply_blocks_auto_move(self.sent, replies[self.contact]))
        self.path.write_text(json.dumps([self.receipt(ts=str((recheck_time + timedelta(seconds=1)).timestamp()))]))
        with self.assertRaisesRegex(ValueError, "Slack reply is later than as-of, review required"):
            stats.load_slack_replies(self.path, recheck_time, 14)

    def test_incomplete_receipts_require_review(self):
        for field in self.receipt():
            receipt = self.receipt()
            del receipt[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load([receipt])
        for receipt in ({}, [None], [self.receipt(substantive="true")]):
            with self.assertRaises(ValueError):
                self.load(receipt)

    def test_no_receipt_or_send_is_not_an_approval(self):
        self.assertEqual(self.load([]), {})
        self.assertFalse(stats.slack_reply_blocks_auto_move(self.sent, None))
        self.assertFalse(stats.slack_reply_blocks_auto_move(None, self.as_of))

    def test_cli_adds_veto_without_changing_gmail_counts(self):
        self.load([self.receipt()])
        email_path = self.root / "gmail.json"
        email_path.write_text(json.dumps({"email_results": {"emails": [{
            "email_id": "sent", "thread_id": "thread", "from_": "owner@example.com",
            "to": self.contact, "date": self.sent.isoformat(), "subject": "Next steps",
        }]}}))
        output = io.StringIO()
        with patch("sys.stdout", output):
            stats.main(["owner@example.com", str(email_path), "--as-of", self.as_of.isoformat(),
                        "--slack-replies", str(self.path)])
        self.assertIn("slack_reply_blocks_auto_move=true", output.getvalue())
        self.assertIn("unanswered_since_last_substantive=1", output.getvalue())


class SharedSlackContracts(unittest.TestCase):
    def contract(self, owner, name):
        return (ROOT / "workspaces" / owner / "workflows" / name / "CONTEXT.md").read_text()

    def test_exact_shared_policy_and_all_three_routes(self):
        policy = yaml.safe_load((ROOT / "_core" / "policy.yaml").read_text())
        self.assertNotIn("slack_lookback_days", policy["pipeline"])
        self.assertEqual(policy["tooling"]["slack_lookback_days"], 14)
        self.assertEqual(policy["forecast"]["sources"], ["salesforce", "calendar", "gmail", "slack"])
        for owner, name in (("pipeline", "pipeline-review"), ("forecasting", "forecast-weekly"),
                            ("pipeline", "task-triage-speed-run")):
            contract = self.contract(owner, name)
            self.assertIn("_core/slack-evidence.md", contract)
            self.assertIn("policy.tooling.slack_lookback_days", contract)
            self.assertIn('"Search", "Limits"', contract)
        for path in (ROOT / "workspaces").rglob("*.md"):
            self.assertNotIn("policy.pipeline.slack_lookback_days", path.read_text(), str(path))

    def test_triage_guard_is_collected_grouped_and_fresh_rechecked(self):
        folder = ROOT / "workspaces" / "pipeline" / "workflows" / "task-triage-speed-run" / "references"
        collect = (folder / "collect.md").read_text()
        grouping = (folder / "grouping.md").read_text()
        writes = (folder / "writes.md").read_text()
        self.assertIn("--slack-replies <reviewed.json>", collect)
        self.assertIn("puts the Task in Reply received / manual response", collect)
        self.assertIn("positive `slack_reply_blocks_auto_move` veto", grouping)
        self.assertIn("Recheck Slack", writes)
        self.assertIn("fresh reviewed receipts", writes)
        self.assertIn("record a fresh local-offset time as the search window end and helper `--as-of`", writes)
        self.assertIn("triage pre-write reply recheck per `rules#run_start`", writes)
        self.assertIn("closeout_check <saved JSON> --as-of <run start with local offset>", writes)
        self.assertIn("both item 8 checks unchanged", collect)

    def test_interaction_sync_stays_without_slack_and_tracking_is_read_only(self):
        folder = ROOT / "workspaces" / "pipeline" / "workflows" / "interaction-sync"
        for path in folder.rglob("*.md"):
            self.assertNotIn("slack", path.read_text().lower())
        forecast = self.contract("forecasting", "forecast-weekly")
        self.assertIn("Tracking reads no Slack", forecast)
        self.assertIn("tracking writes nothing", forecast)


if __name__ == "__main__":
    unittest.main()
