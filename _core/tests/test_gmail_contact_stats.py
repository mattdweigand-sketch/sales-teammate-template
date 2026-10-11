"""Per-contact stats from saved search_email outputs: schema tolerance and counts."""
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspaces/pipeline/scripts"))
import gmail_contact_stats as stats  # noqa: E402

OWNER = "operator@seller.example"
BUYER = "buyer@example.com"


class ContactStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = self.root / "policy.yaml"
        self.policy.write_text(json.dumps({"tooling": {"internal_domains": ["seller.example", "seller-tools.example"]}}))
        self.counter = 0

    def message(self, from_, to, date, subject="Re: pilot", **extra) -> dict:
        self.counter += 1
        return {
            "email_id": f"m{self.counter}", "thread_id": "t1", "from_": from_, "to": to,
            "date": date, "subject": subject, "snippet": "Thanks, see below.", **extra,
        }

    def save(self, emails: list, as_string: bool = False) -> str:
        payload = {"email_results": {"emails": emails}}
        path = self.root / f"output_{self.counter}.json"
        path.write_text(json.dumps({"result": json.dumps(payload) if as_string else payload}))
        return str(path)

    def run_stats(self, *argv: str) -> str:
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            stats.main([OWNER, *argv, "--policy", str(self.policy), "--as-of", "2026-09-25T09:00:00-07:00"])
        return out.getvalue()

    def block(self, output: str, address: str) -> str:
        return output.split(f"\n{address}\n", 1)[1].split("\n\n", 1)[0]

    def test_string_to_field_attributes_sent_message(self) -> None:
        path = self.save([self.message(OWNER, BUYER, "2026-09-20T10:00:00Z")])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("sent=1 last_sent=2026-09-20", block)
        self.assertIn("unanswered_since_last_substantive=1", block)

    def test_canonical_domain_list_keeps_internal_addresses_excluded(self) -> None:
        canonical = Path(__file__).resolve().parents[2] / "_core/policy.yaml"
        tooling = yaml.safe_load(canonical.read_text())["tooling"]
        self.policy.write_text(json.dumps({"tooling": tooling}))
        self.assertEqual(tooling["internal_domains"], ["seller.example", "seller-tools.example"])
        for domain in tooling["internal_domains"]:
            address = "internal@" + domain
            self.assertTrue(stats.internal(address, tuple(tooling["internal_domains"])))
            path = self.save([self.message(address, OWNER, "2026-09-20T10:00:00Z")])
            self.assertNotIn("\n" + address + "\n", self.run_stats(path))
        self.assertFalse(stats.internal(BUYER, tuple(tooling["internal_domains"])))

    def test_string_result_payload_is_decoded(self) -> None:
        path = self.save([self.message(f"Buyer <{BUYER}>", [OWNER], "2026-09-20T10:00:00Z")], as_string=True)
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("last_inbound=2026-09-20 type=substantive", block)
        self.assertIn("newest_message_id=m1 thread_id=t1", block)

    def test_unanswered_counts_sent_after_last_substantive_inbound(self) -> None:
        path = self.save([
            self.message(OWNER, [BUYER], "2026-09-10T10:00:00Z"),
            self.message(BUYER, [OWNER], "2026-09-11T10:00:00Z"),
            self.message(OWNER, [BUYER], "2026-09-12T10:00:00Z"),
            self.message(OWNER, [BUYER], "2026-09-14T10:00:00Z"),
            self.message(BUYER, [OWNER], "2026-09-15T10:00:00Z", subject="Automatic reply: Re: pilot",
                         snippet="I am out of the office until Monday."),
        ])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("sent=3 last_sent=2026-09-14", block)
        self.assertIn("last_inbound=2026-09-15 type=ooo", block)
        self.assertIn("unanswered_since_last_substantive=2", block)

    def test_outbound_draft_does_not_count_as_sent_or_choose_newest_thread(self) -> None:
        path = self.save([
            self.message(OWNER, BUYER, "2026-09-20T10:00:00Z", labels=["SENT"],
                         email_id="sent", thread_id="sent-thread"),
            self.message(OWNER, BUYER, "2026-09-22T10:00:00Z", labels=["DRAFT"],
                         email_id="draft", thread_id="draft-thread"),
        ])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("sent=1 last_sent=2026-09-20", block)
        self.assertIn("unanswered_since_last_substantive=1", block)
        self.assertIn("newest_message_id=sent thread_id=sent-thread", block)
        self.assertNotIn("draft-thread", block)

    def test_inbound_draft_does_not_reset_unanswered_or_inbound_dates(self) -> None:
        path = self.save([
            self.message(BUYER, OWNER, "2026-09-19T10:00:00Z", labels=["INBOX"]),
            self.message(OWNER, BUYER, "2026-09-20T10:00:00Z", labels=["SENT"],
                         email_id="sent", thread_id="sent-thread"),
            self.message(BUYER, OWNER, "2026-09-22T10:00:00Z", labels=["INBOX", "DRAFT"]),
        ])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("last_inbound=2026-09-19 type=substantive", block)
        self.assertIn("last_substantive=2026-09-19T10:00:00Z", block)
        self.assertIn("unanswered_since_last_substantive=1", block)
        self.assertIn("newest_message_id=sent thread_id=sent-thread", block)

    def test_draft_only_contact_is_not_reported(self) -> None:
        path = self.save([self.message(OWNER, BUYER, "not a date", labels=["DRAFT"])])
        self.assertEqual(self.run_stats(path), "")

    def test_missing_labels_keep_existing_behavior_and_ignore_summary(self) -> None:
        path = self.save([self.message(OWNER, BUYER, "2026-09-20T10:00:00Z",
                                      summary="<labels>['DRAFT']</labels>")])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("sent=1 last_sent=2026-09-20", block)
        self.assertIn("unanswered_since_last_substantive=1", block)

    def test_relay_bounce_is_attributed_and_never_the_reply_thread(self) -> None:
        path = self.save([
            self.message(OWNER, [BUYER], "2026-09-10T10:00:00Z"),
            self.message("mailer-daemon@googlemail.com", [OWNER], "2026-09-10T10:01:00Z",
                         subject="Delivery Status Notification (Failure)",
                         snippet=f"Your message to {BUYER} could not be delivered. Undeliverable.",
                         email_id="bounce", thread_id="t-bounce"),
        ])
        block = self.block(self.run_stats(path, "--only", BUYER), BUYER)
        self.assertIn("type=bounce", block)
        self.assertIn("newest_message_id=m1 thread_id=t1", block)

    def test_only_parses_comma_separated_addresses_and_skips_internal(self) -> None:
        other = "cfo@example.com"
        path = self.save([
            self.message(OWNER, [BUYER, other, "colleague@seller.example"], "2026-09-20T10:00:00Z"),
            self.message(OWNER, ["ignored@example.com"], "2026-09-20T11:00:00Z"),
        ])
        out = self.run_stats(path, "--only", f"{BUYER}, {other.upper()}")
        self.assertIn(f"\n{BUYER}\n", out)
        self.assertIn(f"\n{other}\n", out)
        self.assertNotIn("ignored@example.com", out)
        self.assertNotIn("colleague@seller.example", out)

    def test_files_are_required(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            stats.main([OWNER, "--only", BUYER])


    def test_offset_dates_order_by_instant(self):
        path=self.save([
            self.message(OWNER,BUYER,"2026-09-21T15:30:00Z",email_id="sent"),
            self.message(BUYER,OWNER,"2026-09-21T09:00:00-07:00",email_id="reply"),
        ])
        out=self.run_stats(path,"--only",BUYER)
        self.assertIn("unanswered_since_last_substantive=0",out)
        self.assertIn("newest_message_id=reply",out)

    def test_substantive_body_and_quoted_ooo_do_not_override_reply(self):
        for subject,body in (("Delivery status dashboard","Please send a quote."),
                             ("Re: pilot","I am away from my desk but our contract is approved."),
                             ("Re: pilot","Approved. On Monday I wrote: Automatic reply, out of office.")):
            self.assertEqual(stats.kind_of({"subject":subject,"body":body,"from_":BUYER}),"substantive")

    def test_midnight_summary_uses_run_local_date(self):
        path=self.save([self.message(OWNER,BUYER,"2026-09-25T06:30:00Z")])
        self.assertIn("last_sent=2026-09-24",self.run_stats(path))
        path=self.save([self.message(BUYER,OWNER,"Fri, 25 Sep 2026 06:30:00 +0000")])
        self.assertIn("last_inbound=2026-09-24",self.run_stats(path))

    def test_unknown_date_stops_for_review(self):
        path=self.save([self.message(BUYER,OWNER,"not a date")])
        with self.assertRaisesRegex(ValueError,"review required"):
            self.run_stats(path)

class SendHoldTimestampTests(unittest.TestCase):
    def test_one_instant_before_equality_and_after_boundary(self):
        sent = datetime(2026, 10, 8, 20, 46, tzinfo=timezone(timedelta(hours=-7)))
        boundary = sent + timedelta(hours=24)
        for delta, blocked in ((-1, True), (0, False), (1, False)):
            with self.subTest(seconds_from_boundary=delta):
                self.assertEqual(
                    stats.sent_mail_hold_blocks_draft(sent, boundary + timedelta(seconds=delta), 1),
                    blocked,
                )

    def test_two_day_cold_hold_is_distinct_from_one_day_active_hold(self):
        sent = datetime(2026, 10, 8, 20, 46, tzinfo=timezone.utc)
        as_of = sent + timedelta(hours=24)
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, as_of, 1))
        self.assertTrue(stats.sent_mail_hold_blocks_draft(sent, as_of, 2))
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, sent + timedelta(hours=48), 2))

    def test_spring_dst_change_does_not_release_at_23_elapsed_hours(self):
        pacific = ZoneInfo("America/Los_Angeles")
        sent = datetime(2026, 3, 7, 12, tzinfo=pacific)
        same_clock_next_day = datetime(2026, 3, 8, 12, tzinfo=pacific)
        self.assertTrue(stats.sent_mail_hold_blocks_draft(sent, same_clock_next_day, 1))
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, datetime(2026, 3, 8, 13, tzinfo=pacific), 1))

    def test_fall_dst_change_uses_elapsed_hours_not_wall_clock_days(self):
        pacific = ZoneInfo("America/Los_Angeles")
        sent = datetime(2026, 10, 31, 12, tzinfo=pacific)
        self.assertTrue(stats.sent_mail_hold_blocks_draft(sent, datetime(2026, 11, 1, 10, 59, 59, tzinfo=pacific), 1))
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, datetime(2026, 11, 1, 11, tzinfo=pacific), 1))
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, datetime(2026, 11, 1, 12, tzinfo=pacific), 1))

    def test_equivalent_offsets_compare_as_instants(self):
        sent = datetime.fromisoformat("2026-10-08T20:46:00-07:00")
        self.assertFalse(stats.sent_mail_hold_blocks_draft(sent, datetime.fromisoformat("2026-10-10T03:46:00+00:00"), 1))

    def test_no_previous_send_has_no_send_hold_but_is_not_recipient_permission(self):
        self.assertFalse(stats.sent_mail_hold_blocks_draft(None, datetime(2026, 10, 8, tzinfo=timezone.utc), 1))

    def test_naive_future_and_invalid_duration_inputs_stop_for_review(self):
        aware = datetime(2026, 10, 8, tzinfo=timezone.utc)
        for sent, as_of, days in (
            (aware.replace(tzinfo=None), aware, 1),
            (aware, aware.replace(tzinfo=None), 1),
            (None, aware.replace(tzinfo=None), 1),
            (aware + timedelta(seconds=1), aware, 1),
            (aware, aware, -1),
            (aware, aware, True),
            (aware, aware, 1.5),
        ):
            with self.subTest(sent=sent, as_of=as_of, days=days), self.assertRaises(ValueError):
                stats.sent_mail_hold_blocks_draft(sent, as_of, days)

    def output(self, messages, as_of="2026-10-09T20:11:00-07:00"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "policy.yaml"
            policy.write_text(json.dumps({
                "tooling": {"internal_domains": ["seller.example"]},
                "followup": {"sent_mail_hold_days_active": 1, "sent_mail_hold_days_cold": 2},
            }))
            source = root / "output_email.json"
            source.write_text(json.dumps({"email_results": {"emails": messages}}))
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                stats.main([OWNER, str(source), "--policy", str(policy), "--as-of", as_of, "--send-hold"])
            return out.getvalue()

    def sent(self, timestamp, **extra):
        return {"email_id": "sent", "thread_id": "thread", "from_": OWNER, "to": BUYER,
                "date": timestamp, "subject": "Follow-up", "labels": ["SENT"], **extra}

    def test_cli_uses_native_timestamp_not_a_calendar_date_boundary(self):
        output = self.output([self.sent("2026-10-08T20:46:00-07:00")])
        self.assertIn("last_sent_at=2026-10-08T20:46:00-07:00", output)
        self.assertIn("send_hold_active=true", output)
        self.assertIn("send_hold_cold=true", output)
        equality = self.output([self.sent("2026-10-08T20:46:00-07:00")], "2026-10-09T20:46:00-07:00")
        self.assertIn("send_hold_active=false", equality)
        self.assertIn("send_hold_cold=true", equality)

    def test_cli_latest_actual_send_wins_and_draft_does_not_start_hold(self):
        output = self.output([
            self.sent("2026-10-06T20:46:00-07:00", email_id="older"),
            self.sent("2026-10-07T20:46:00-07:00", email_id="newer"),
            self.sent("2026-10-09T20:00:00-07:00", email_id="draft", labels=["DRAFT"]),
        ])
        self.assertIn("last_sent_at=2026-10-07T20:46:00-07:00", output)
        self.assertIn("send_hold_active=false", output)
        self.assertIn("send_hold_cold=true", output)

    def test_cli_rejects_date_only_sent_value(self):
        with self.assertRaises(ValueError):
            self.output([self.sent("2026-10-08")])


if __name__ == "__main__":
    unittest.main()
