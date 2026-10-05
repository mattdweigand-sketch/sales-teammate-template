"""Regression checks for next-step sentences, event timing, and linked activity."""
import datetime as dt
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "scripts"))
import hygiene_check as hygiene  # noqa: E402


ONE_TASK = {"Id": "task-1", "WhatId": "opp-1", "ActivityDate": "2026-09-30", "IsClosed": False, "Subject": "Follow up"}


class PipelineTimingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_of = dt.datetime.fromisoformat("2026-09-21T07:00:31-07:00")
        self.policy = {
            "pipeline": {
                "stages": ["S2"], "required_fields": {}, "conditional_fields": [],
                "close_warning_days": 14, "date_at_risk_below_stage": "S3", "stale_days": 14,
            }
        }
        self.opp = {
            "Id": "opp-1", "AccountId": "account-1", "StageName": "S2 - Solutioning",
            "CloseDate": "2026-12-31",
            "Next_Steps__c": "9/19/26 SR - Discuss evaluation on 9/21.",
        }

    def event(self, start: str | None, end: str | None) -> dict:
        return {
            "Id": "event-1", "AccountId": "account-1", "WhatId": "account-1",
            "ActivityDate": "2026-09-21", "StartDateTime": start, "EndDateTime": end,
            "Subject": "Search discussion",
        }

    def result(self, events: list, tasks: list | None = None) -> dict:
        acts = hygiene.index_activity(tasks or [], events, self.as_of.tzinfo)
        return hygiene.check(self.opp, self.policy, acts, self.as_of)

    def test_later_today_event_is_upcoming_not_new_activity(self) -> None:
        result = self.result([self.event("2026-09-21T21:00:00Z", "2026-09-21T21:45:00Z")])
        self.assertNotIn("new_activity", result["triggers"])
        self.assertIsNone(result["last_activity"])
        self.assertEqual(result["upcoming_event_evidence"]["timing"], "upcoming")

    def test_ongoing_meeting_is_not_completed(self) -> None:
        result = self.result([self.event("2026-09-21T13:50:00Z", "2026-09-21T14:30:00Z")])
        self.assertNotIn("new_activity", result["triggers"])
        self.assertEqual(result["upcoming_event_evidence"]["timing"], "in_progress")

    def test_ended_event_is_elapsed_not_proof_of_attendance(self) -> None:
        result = self.result([self.event("2026-09-21T12:00:00Z", "2026-09-21T12:30:00Z")])
        self.assertIn("new_activity", result["triggers"])
        self.assertEqual(result["new_activity_evidence"]["timing"], "elapsed")
        self.assertEqual(result["unverified_events"][0]["id"], "event-1")
        self.assertIn("attendance unverified", hygiene.fmt(result))

    def test_event_ending_at_cutoff_is_elapsed(self) -> None:
        result = self.result([self.event("2026-09-21T13:00:00Z", "2026-09-21T14:00:31Z")])
        self.assertIn("new_activity", result["triggers"])

    def test_date_only_today_is_not_held(self) -> None:
        result = self.result([self.event(None, None)])
        self.assertNotIn("new_activity", result["triggers"])
        self.assertEqual(result["unverified_events"][0]["timing"], "timing_unknown")

    def test_date_only_past_is_not_proof_of_completion(self) -> None:
        event = self.event(None, None)
        event["ActivityDate"] = "2026-09-20"
        self.assertNotIn("new_activity", self.result([event])["triggers"])

    def test_missing_end_after_start_requires_verification(self) -> None:
        result = self.result([self.event("2026-09-21T13:00:00Z", None)])
        self.assertNotIn("new_activity", result["triggers"])

    def test_end_before_start_requires_verification(self) -> None:
        result = self.result([self.event("2026-09-21T13:00:00Z", "2026-09-21T12:00:00Z")])
        self.assertNotIn("new_activity", result["triggers"])

    def test_naive_datetime_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            hygiene.parse_activity_timestamp("2026-09-21T07:00:00")

    def test_utc_midnight_uses_run_local_date(self) -> None:
        result = self.result([self.event("2026-09-21T01:00:00Z", "2026-09-21T01:30:00Z")])
        self.assertEqual(result["new_activity_evidence"]["date"], "2026-09-20")

    def test_account_linked_inbound_is_last_touch_and_deduplicated(self) -> None:
        task = {
            "Id": "inbound-1", "WhatId": "account-1", "AccountId": "account-1",
            "ActivityDate": "2026-09-21", "IsClosed": True,
            "Subject": "Email: << Credential request", "Who": {"Name": "Buyer"},
        }
        result = self.result([], [task])
        self.assertIn("new_activity", result["triggers"])
        self.assertEqual(result["last_activity_evidence"]["id"], "inbound-1")
        self.assertEqual(result["last_activity_evidence"]["contact"], "Buyer")
        self.assertEqual(result["new_activity_evidence"]["what_id"], "account-1")

    def test_open_inbound_task_is_not_a_completed_touch(self) -> None:
        task = {
            "Id": "task-1", "WhatId": "opp-1", "ActivityDate": "2026-09-21",
            "IsClosed": False, "Subject": "Email: << Inbound",
        }
        self.assertNotIn("new_activity", self.result([], [task])["triggers"])

    def test_outbound_is_last_touch_but_not_new_buyer_activity(self) -> None:
        task = {
            "Id": "task-1", "WhatId": "opp-1", "ActivityDate": "2026-09-21",
            "IsClosed": True, "Subject": "Email: >> Sent",
        }
        result = self.result([], [task])
        self.assertNotIn("new_activity", result["triggers"])
        self.assertEqual(result["last_activity_evidence"]["id"], "task-1")

    def test_upcoming_event_clears_stale_without_becoming_a_touch(self) -> None:
        self.opp["Next_Steps__c"] = None
        result = self.result([self.event("2026-09-21T18:00:00Z", "2026-09-21T18:30:00Z")])
        self.assertNotIn("stale", result["triggers"])
        self.assertIsNone(result["last_activity"])

    def test_unchanged_future_action_is_not_overdue(self) -> None:
        self.assertNotIn("next_passed", self.result([])["triggers"])

    def test_passed_next_step_with_no_activity_is_stale(self) -> None:
        self.opp["Next_Steps__c"] = "9/1/26 SR - Follow up with the buyer by 9/5."
        result = self.result([])
        self.assertIn("next_passed", result["triggers"])
        self.assertIn("stale", result["triggers"])

    def test_passed_close_date_is_date_at_risk_at_any_stage(self) -> None:
        self.opp["StageName"] = "S4 - Testing"
        self.policy["pipeline"]["stages"] = ["S2", "S3", "S4", "S5"]
        self.opp["CloseDate"] = "2026-09-20"
        self.assertIn("date_at_risk", self.result([])["triggers"])

    def test_close_date_within_warning_window_below_gate_is_date_at_risk(self) -> None:
        self.opp["CloseDate"] = "2026-10-05"   # 14 days out, S2 is below S3
        self.assertIn("date_at_risk", self.result([])["triggers"])
        self.opp["CloseDate"] = "2026-10-06"   # 15 days out
        self.assertNotIn("date_at_risk", self.result([])["triggers"])

    def test_close_date_within_warning_window_at_or_above_gate_is_not_date_at_risk(self) -> None:
        self.policy["pipeline"]["stages"] = ["S2", "S3", "S4", "S5"]
        self.opp["StageName"] = "S3 - Validation"
        self.opp["CloseDate"] = "2026-10-05"
        self.assertNotIn("date_at_risk", self.result([])["triggers"])

    def test_required_and_conditional_blank_fields_follow_policy(self) -> None:
        self.policy["pipeline"]["stages"] = ["S2", "S3", "S4", "S5"]
        self.policy["pipeline"]["required_fields"] = {
            "S2": ["Amount", "LeadSource"], "S3": ["Contract_Status__c"], "S4": [], "S5": ["Contract_Sent__c"],
        }
        self.policy["pipeline"]["conditional_fields"] = [
            {"field": "Trial_Expiration_Date__c", "when": {"Deal_Type__c": "Paid Trial"}},
        ]
        self.opp.update({
            "StageName": "S3 - Validation", "Amount": 0, "LeadSource": "Web",
            "Contract_Status__c": None, "Deal_Type__c": "Paid Trial",
        })
        result = self.result([])
        self.assertEqual(result["blank_fields"], ["Amount", "Contract_Status__c", "Trial_Expiration_Date__c"])
        self.assertIn("blank_field", result["triggers"])
        self.opp["Deal_Type__c"] = "New Business"
        self.assertNotIn("Trial_Expiration_Date__c", self.result([])["blank_fields"])

    def test_note_prefix_from_policy_drives_note_and_entry_regexes(self) -> None:
        self.policy["salesforce"] = {"note_prefix": "M/D/YY AB | "}
        self.opp["Next_Steps__c"] = "9/19/26 AB | Send the agreement by 9/25.\n9/18/26 SR - Old prefix."
        result = self.result([])
        self.assertEqual(result["next"], "OK")
        self.assertEqual(result["next_date"], "2026-09-25")
        self.assertEqual(result["newest_note"], "2026-09-19")
        self.policy["salesforce"] = {"note_prefix": "M/D/YY SR - "}
        self.assertEqual(self.result([])["next"], "MISSING")


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.policy = root / "policy.yaml"
        self.policy.write_text(json.dumps({"pipeline": {
            "stages": ["S2"], "required_fields": {}, "conditional_fields": [],
            "close_warning_days": 14, "date_at_risk_below_stage": "S3", "stale_days": 14,
            "triggers": ["next_passed", "new_activity", "blank_field", "date_at_risk", "stale"],
        }}))
        self.opps = root / "opps.json"
        self.opps.write_text(json.dumps({"result": json.dumps({"records": [{
            "attributes": {"type": "Opportunity"}, "Id": "opp-1", "AccountId": "account-1", "StageName": "S2 - Solutioning",
            "CloseDate": "2026-12-31", "Next_Steps__c": "9/20/26 SR - Send the agreement by 9/25.",
        }]})}))

    def run_main(self, *extra: str) -> str:
        out = io.StringIO()
        with mock.patch("sys.argv", ["hygiene_check.py", str(self.opps), "--policy", str(self.policy), *extra]):
            with mock.patch("sys.stdout", out):
                hygiene.main()
        return out.getvalue()

    def test_as_of_sets_the_local_date(self) -> None:
        out = self.run_main("--as-of", "2026-09-21T18:00:00-07:00")
        self.assertIn("-- 1 open deals as of 2026-09-21. In scope: 1.", out)

    def test_as_of_is_required(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            self.run_main()
        self.assertEqual(ctx.exception.code, 2)

    def test_mislabeled_object_files_fail_before_output(self) -> None:
        for argument, expected, wrong, prefix in (
            ("opps", "Opportunity", "Task", "00T"),
            ("--tasks", "Task", "Event", "00U"),
            ("--events", "Event", "Task", "00T"),
        ):
            for metadata in (True, False):
                with self.subTest(argument=argument, metadata=metadata):
                    path = self.opps.parent / "wrong.json"
                    row = {"Id": prefix + "AAA000000001AAA"}
                    if metadata:
                        row["attributes"] = {"type": wrong}
                    path.write_text(json.dumps({"result": json.dumps({"records": [row], "done": True})}))
                    original = self.opps
                    if argument == "opps":
                        self.opps = path
                    extra = [] if argument == "opps" else [argument, str(path)]
                    stderr, stdout = io.StringIO(), io.StringIO()
                    with mock.patch("sys.argv", ["hygiene_check.py", str(self.opps), "--policy", str(self.policy),
                                                 "--as-of", "2026-09-29T07:00:00-07:00", *extra]), \
                            redirect_stderr(stderr), mock.patch("sys.stdout", stdout), self.assertRaises(SystemExit) as ctx:
                        hygiene.main()
                    self.opps = original
                    self.assertEqual(ctx.exception.code, 2)
                    self.assertIn(f"expected {expected} records", stderr.getvalue())
                    self.assertIn(argument, stderr.getvalue())
                    self.assertEqual(stdout.getvalue(), "")

    def test_typed_input_accepts_metadata_or_id_and_empty_records(self) -> None:
        path = self.opps.parent / "tasks.json"
        for rows in ([], [{"Id": "00TAAA000000001AAA"}],
                     [{"Id": "synthetic", "attributes": {"type": "Task"}}]):
            with self.subTest(rows=rows):
                path.write_text(json.dumps({"records": rows}))
                self.assertEqual(hygiene.load_typed_records(path, "Task", "--tasks"), rows)

    def test_typed_input_rejects_mixed_unknown_and_conflicting_records(self) -> None:
        path = self.opps.parent / "tasks.json"
        for invalid in ({"Id": "00UAAA000000001AAA"}, {"Id": "unknown"},
                        {"Id": "00UAAA000000001AAA", "attributes": {"type": "Task"}}):
            with self.subTest(invalid=invalid):
                path.write_text(json.dumps([{"Id": "00TAAA000000001AAA"}, invalid]))
                with self.assertRaisesRegex(ValueError, "expected Task records"):
                    hygiene.load_typed_records(path, "Task", "--tasks")


class DatedNextStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_of = dt.datetime.fromisoformat("2026-09-22T15:28:00-07:00")
        self.policy = {
            "pipeline": {
                "stages": ["S2"], "required_fields": {}, "conditional_fields": [],
                "close_warning_days": 14, "date_at_risk_below_stage": "S3", "stale_days": 14,
            }
        }

    def check_text(self, text: str | None, tasks: list | None = None, events: list | None = None) -> dict:
        opportunity = {
            "Id": "opp-1", "AccountId": "account-1", "StageName": "S2 - Solutioning",
            "CloseDate": "2026-12-31", "Next_Steps__c": text,
        }
        activity = hygiene.index_activity(tasks or [], events or [], self.as_of.tzinfo)
        return hygiene.check(opportunity, self.policy, activity, self.as_of)

    def test_approved_sentence_uses_action_date_not_entry_date(self) -> None:
        text = (
            "9/22/26 SR - Follow up with Andrew on 9/24 for order form feedback, "
            "an admin introduction, signer, and decision date."
        )
        result = self.check_text(text)
        self.assertEqual(result["next"], "OK")
        self.assertEqual(result["next_format"], "dated_sentence")
        self.assertEqual(result["next_date"], "2026-09-24")
        self.assertEqual(result["newest_note"], "2026-09-22")
        self.assertEqual(result["next_action"], text.split(" SR - ", 1)[1])
        self.assertNotIn("next_owner", result)
        self.assertNotIn("next_passed", result["triggers"])
        self.assertNotIn("stale", result["triggers"])
        self.assertNotIn("blank_field", result["triggers"])
        self.assertTrue(result["task_gap"])
        self.assertIn("OK 2026-09-24 (Follow up", hygiene.fmt(result))

    def test_full_year_and_by_are_supported(self) -> None:
        result = self.check_text("9/22/26 SR - Send the agreement by 9/25/2026.")
        self.assertEqual(result["next_date"], "2026-09-25")

    def test_overdue_sentence_preserves_due_date_check(self) -> None:
        result = self.check_text("9/22/26 SR - Follow up with Andrew by 9/21.", [ONE_TASK])
        self.assertEqual(result["next_passed_days"], 1)
        self.assertIn("next_passed", result["triggers"])
        self.assertFalse(result["task_gap"])  # one open Task; no live date to compare

    def test_old_written_date_with_future_deadline_is_not_overdue(self) -> None:
        result = self.check_text("9/10/26 SR - Send the agreement on 9/24.")
        self.assertNotIn("next_passed", result["triggers"])

    def test_cross_year_deadline_uses_explicit_year(self) -> None:
        result = self.check_text("12/30/26 SR - Send the agreement by 1/2/27.")
        self.assertEqual(result["next_date"], "2027-01-02")

    def test_yearless_deadline_uses_written_year_not_run_year(self) -> None:
        result = self.check_text("12/30/25 SR - Send the agreement by 12/31.")
        self.assertEqual(result["next_date"], "2025-12-31")

    def test_missing_deadline_never_uses_written_date(self) -> None:
        result = self.check_text("9/22/26 SR - Follow up with Andrew.", [ONE_TASK])
        self.assertEqual(result["next"], "REVIEW")
        self.assertNotIn("next_date", result)
        self.assertIn("blank_field", result["triggers"])
        self.assertFalse(result["task_gap"])  # one open Task; no live date to compare
        self.assertIn("No explicit on/by", hygiene.fmt(result))

    def test_multiple_possible_deadlines_require_review(self) -> None:
        result = self.check_text(
            "9/22/26 SR - Send the agreement on 9/24 after the email on 9/21."
        , [ONE_TASK])
        self.assertEqual(result["next"], "REVIEW")
        self.assertNotIn("next_date", result)
        self.assertNotIn("next_passed", result["triggers"])
        self.assertFalse(result["task_gap"])  # one open Task; no live date to compare

    def test_invalid_due_date_requires_review_without_crashing(self) -> None:
        result = self.check_text("9/22/26 SR - Send the agreement on 9/31.")
        self.assertEqual(result["next"], "REVIEW")
        self.assertIn("Invalid action due date", result["next_review_reason"])

    def test_invalid_written_date_requires_review_without_crashing(self) -> None:
        result = self.check_text("9/31/26 SR - Send the agreement on 10/1.")
        self.assertEqual(result["next"], "REVIEW")
        self.assertIsNone(result["newest_note"])

    def test_legacy_next_line_is_review_not_parsed(self) -> None:
        result = self.check_text(
            "Next: Send agreement · Operator · 9/24/26\n9/20/26 SR - Buyer replied."
        )
        self.assertEqual(result["next"], "REVIEW")
        self.assertEqual(result["next_review_reason"], "Legacy Next: line; rewrite as a dated entry")
        self.assertNotIn("next_date", result)
        self.assertIn("blank_field", result["triggers"])
        self.assertEqual(result["newest_note"], "2026-09-20")

    def test_historical_action_entries_do_not_override_current_deadline(self) -> None:
        result = self.check_text(
            "9/22/26 SR - Send the agreement on 9/24.\n"
            "9/21/26 SR - Follow up with Andrew on 9/21.\n"
            "9/18/26 SR - Buyer replied on 9/17."
        )
        self.assertEqual(result["next_date"], "2026-09-24")
        self.assertNotIn("next_passed", result["triggers"])

    def test_task_gap_needs_exactly_one_open_task(self) -> None:
        text = "9/22/26 SR - Follow up with Andrew on 9/24."
        on_date = dict(ONE_TASK, ActivityDate="2026-09-24")
        self.assertIn("task_gap", self.check_text(text)["triggers"])
        self.assertNotIn("task_gap", self.check_text(text, [on_date])["triggers"])
        self.assertIn("task_gap", self.check_text(text, [on_date, dict(on_date, Id="task-2")])["triggers"])

    def test_task_gap_matches_action_date_not_entry_date(self) -> None:
        text = "9/22/26 SR - Follow up with Andrew on 9/24."
        task = {
            "Id": "task-1", "WhatId": "opp-1", "ActivityDate": "2026-09-22",
            "IsClosed": False, "Subject": "Follow up with Andrew",
        }
        self.assertTrue(self.check_text(text, [task])["task_gap"])
        task["ActivityDate"] = "2026-09-24"
        self.assertFalse(self.check_text(text, [task])["task_gap"])

    def test_interim_followup_can_coexist_with_later_event_milestone_pending_review(self) -> None:
        text = "9/22/26 SR - Reply to the buyer by 9/30."
        milestone = dict(ONE_TASK, Id="task-2", ActivityDate="2026-10-07", Subject="Readout")
        event = {"Id": "event-1", "WhatId": "opp-1", "Subject": "Readout",
                 "StartDateTime": "2026-10-07T17:00:00Z", "EndDateTime": "2026-10-07T18:00:00Z"}
        result = self.check_text(text, [ONE_TASK, milestone], [event])
        self.assertFalse(result["task_gap"])
        self.assertTrue(result["task_review_required"])
        self.assertEqual(result["milestone_task_candidates"][0]["task"]["id"], "task-2")
        self.assertEqual(result["milestone_task_candidates"][0]["events"][0]["id"], "event-1")
        self.assertIn("milestone task review", hygiene.fmt(result))
        # A milestone cannot stand in for the current-action Task; duplicate or
        # undated later Tasks and unrelated/date-only Events do not qualify.
        cases = [([milestone], [event]), ([ONE_TASK, milestone], []),
                 ([ONE_TASK, milestone, dict(milestone, Id="task-3")], [event]),
                 ([ONE_TASK, dict(milestone, ActivityDate=None)], [event]),
                 ([ONE_TASK, milestone], [dict(event, WhatId="other")]),
                 ([ONE_TASK, milestone], [{"Id": "event-1", "WhatId": "opp-1", "ActivityDate": "2026-10-07"}])]
        for tasks, events in cases:
            with self.subTest(tasks=tasks, events=events):
                self.assertTrue(self.check_text(text, tasks, events)["task_gap"])

    def test_empty_and_undated_entries_remain_missing(self) -> None:
        for text in (None, "", "Follow up with Andrew on 9/24."):
            with self.subTest(text=text):
                self.assertEqual(self.check_text(text)["next"], "MISSING")

    def test_html_paragraphs_keep_history_on_separate_lines(self) -> None:
        result = self.check_text(
            "<p>9/22/26 SR - Follow up with Andrew on 9/24.</p>"
            "<p>9/20/26 SR - Buyer replied.</p>"
        )
        self.assertEqual(result["next"], "OK")
        self.assertEqual(result["next_date"], "2026-09-24")


    def test_every_live_action_requires_semantic_task_review(self):
        text="9/22/26 SR - Follow up with Andrew on 9/24."
        task={"Id":"t1","WhatId":"opp-1","WhoId":"c1","ActivityDate":"2026-09-25","IsClosed":False,"Subject":"Follow up with Andrew"}
        result=self.check_text(text,[task])
        self.assertTrue(result["task_gap"])
        self.assertTrue(result["task_review_required"])
        self.assertEqual(result["open_task_candidates"][0]["contact_id"],"c1")
        task.update(ActivityDate="2026-09-24",Subject="Unrelated action")
        result=self.check_text(text,[task])
        self.assertFalse(result["task_gap"])
        self.assertTrue(result["task_review_required"])

if __name__ == "__main__":
    unittest.main()
