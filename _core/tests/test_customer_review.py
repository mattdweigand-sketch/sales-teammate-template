"""Synthetic customer milestone, renewal, receipt and migration regressions."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workspaces/pipeline/workflows/customer-review"
sys.path.insert(0, str(WORKFLOW / "scripts"))
from customer_review import calendar_months_after, review_customers, schedule_occurrence

AS_OF = "2026-10-05T07:30:00-07:00"
WINDOW_START = "2026-09-07T07:30:00-07:00"


class CustomerReviewTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.evidence = {
            "owner_id": "owner", "accounts_complete": True, "opportunities_complete": True,
            "accounts": [{"Id": "account", "Name": "Synthetic Customer", "OwnerId": "owner",
                          "Admin_Organization_UUID__c": "org", "Org_UUID__c": "org"}],
            "opportunities": [{"Id": "won", "AccountId": "account", "OwnerId": "another-owner", "IsClosed": True,
                               "IsWon": True, "Deal_Type__c": "New Business", "CloseDate": "2026-07-04",
                               "Subscription_Cancel_Date__c": "2027-01-15"}],
            "usage": {"account": {"org_uuid": "org", "data_through": "2026-10-04", "complete": True, "billed_seats": 5,
                                  "weekly_trend": [{"week_start": "2026-09-28", "active_users": 1, "queries": 8}],
                                  "feature_mix": [{"kind": "mode", "value": "asi", "queries": 8, "users": 1}],
                                  "rows": [{"user_email": "active@example.test", "window_queries": 8, "l7_queries": 2},
                                           {"user_email": "idle@example.test", "window_queries": 0, "l7_queries": 0}]}},
        }

    def review(self, **arguments):
        return review_customers(self.evidence, AS_OF, self.policy, **arguments)

    def row(self, **arguments):
        return self.review(**arguments)["accounts"][0]

    def receipt_entry(self, months=3, milestone_date="2026-10-04", reviewed=False):
        entry = {"account_id": "account", "milestone_months": months, "milestone_date": milestone_date}
        if reviewed:
            entry["receipt_date"] = "2026-10-04T15:00:00-07:00"
        return entry

    def test_month_end_clamping_and_leap_year(self):
        for anchor, months, expected in (("2025-01-31", 1, "2025-02-28"), ("2024-01-31", 1, "2024-02-29"),
                                         ("2023-08-31", 6, "2024-02-29"), ("2024-08-31", 6, "2025-02-28")):
            self.assertEqual(calendar_months_after(date.fromisoformat(anchor), months).isoformat(), expected)
        for invalid in (True, 0, -1, 3.5):
            with self.assertRaises(ValueError):
                calendar_months_after(date(2026, 1, 1), invalid)

    def test_first_win_across_all_owners_anchors_and_later_wins_never_reset_age(self):
        later = {**self.evidence["opportunities"][0], "Id": "later", "CloseDate": "2026-09-01"}
        self.evidence["opportunities"].append(later)
        row = self.row()
        self.assertEqual(row["anchor"], {"date": "2026-07-04", "opportunity_ids": ["won"]})
        self.assertEqual((row["milestone"]["months"], row["milestone"]["date"]), (3, "2026-10-04"))
        self.assertEqual(row["won_opportunity_ids"], ["later", "won"])

    def test_paid_trial_is_not_an_anchor_or_customer(self):
        trial = {**self.evidence["opportunities"][0], "Id": "trial", "Deal_Type__c": "Paid Trial", "CloseDate": "2025-01-01"}
        self.evidence["opportunities"].append(trial)
        self.assertEqual(self.row()["anchor"]["date"], "2026-07-04")
        self.evidence["opportunities"] = [trial]
        self.assertEqual(self.review()["accounts"], [])

    def test_missing_invalid_future_or_conflicting_anchor_never_computes_milestone(self):
        for value in (None, "bad", "2026-02-30", "2027-01-01"):
            with self.subTest(value=value):
                evidence = copy.deepcopy(self.evidence)
                evidence["opportunities"][0]["CloseDate"] = value
                row = review_customers(evidence, AS_OF, self.policy)["accounts"][0]
                self.assertIsNone(row["milestone"])
                self.assertTrue(any("CloseDate" in reason for reason in row["needs_input"]))
        self.evidence["opportunities"].append({**self.evidence["opportunities"][0], "CloseDate": "2026-06-01"})
        row = self.row()
        self.assertIsNone(row["anchor"])
        self.assertTrue(any("conflicting" in reason for reason in row["needs_input"]))

    def test_missing_nontrial_anchor_on_demand_is_needs_input(self):
        self.evidence["opportunities"] = []
        row = self.row(account_id="account")
        self.assertIsNone(row["milestone"])
        self.assertIn("first verified non-trial Closed Won anchor missing", row["needs_input"])

    def test_nontrial_status_requires_the_queried_deal_type_field(self):
        del self.evidence["opportunities"][0]["Deal_Type__c"]
        row = self.row()
        self.assertIsNone(row["milestone"])
        self.assertTrue(any("non-trial status" in reason for reason in row["needs_input"]))

    def test_window_window_start_exclusive_as_of_inclusive(self):
        boundary = "2026-10-04T00:00:00-07:00"
        before = "2026-10-03T23:59:59-07:00"
        due = review_customers(self.evidence, boundary, self.policy, window_start=before)["accounts"][0]
        self.assertEqual(due["milestone"]["status"], "due")
        excluded = self.row(window_start=boundary)
        self.assertEqual(excluded["milestone"]["status"], "not_due")
        with self.assertRaisesRegex(ValueError, "before"):
            self.review(window_start=AS_OF)

    def test_first_run_uses_previous_policy_occurrence_and_timezone(self):
        result = self.review()
        self.assertEqual(result["window"]["window_start"], WINDOW_START)
        self.assertEqual(result["window"]["source"], "previous_policy_occurrence")
        schedule = self.policy["pipeline"]["customer_review"]["schedule"]
        moment = datetime(2026, 11, 2, 7, 30, tzinfo=ZoneInfo(schedule["tz"]))
        self.assertEqual(schedule_occurrence(moment, schedule, -1).isoformat(), AS_OF)
        utc = review_customers(self.evidence, "2026-10-05T14:30:00+00:00", self.policy)
        self.assertEqual(utc["window"]["as_of"], AS_OF)

    def test_catch_up_selects_latest_and_supersedes_earlier_milestones(self):
        self.evidence["opportunities"][0]["CloseDate"] = "2025-10-04"
        row = self.row(window_start="2025-12-01T00:00:00-08:00")
        self.assertEqual((row["milestone"]["months"], row["milestone"]["status"]), (12, "due"))
        self.assertEqual([(item["months"], item["status"]) for item in row["superseded"]], [(3, "superseded"), (6, "superseded")])

    def test_next_window_does_not_repeat_milestone(self):
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = "2027-08-01"
        self.assertEqual(self.row(window_start=WINDOW_START)["milestone"]["status"], "due")
        next_run = review_customers(self.evidence, "2026-11-02T07:30:00-08:00", self.policy, window_start=AS_OF)
        self.assertEqual(next_run["accounts"], [])
        self.assertEqual(next_run["not_due_count"], 1)

    def test_no_receipt_fallback_covers_the_prior_nominal_period_at_late_starts(self):
        moments = ["2026-10-05T07:30:00-07:00", "2026-10-05T07:30:01-07:00", "2026-10-05T07:31:00-07:00",
                   "2026-10-05T08:00:00-07:00", "2026-10-06T09:00:00-07:00", "2026-10-20T09:00:00-07:00"]
        for moment in moments:
            with self.subTest(as_of=moment):
                result = review_customers(self.evidence, moment, self.policy)
                self.assertEqual(result["window"]["window_start"], WINDOW_START)
                self.assertEqual(result["window"]["as_of"], moment)
                self.assertEqual(result["accounts"][0]["milestone"]["status"], "due")

    def test_receipt_boundary_is_unchanged_when_run_starts_seconds_late(self):
        receipt_as_of = "2026-09-07T07:31:00-07:00"
        result = review_customers(self.evidence, "2026-10-05T07:30:01-07:00", self.policy, window_start=receipt_as_of)
        self.assertEqual(result["window"]["window_start"], receipt_as_of)
        self.assertEqual(result["window"]["source"], "scheduled_receipt")
        self.assertEqual(result["accounts"][0]["milestone"]["status"], "due")

    def test_on_demand_latest_only_one_account_and_explicit_reassessment(self):
        self.evidence["opportunities"][0]["CloseDate"] = "2025-10-04"
        self.evidence["accounts"].append({"Id": "other", "Name": "Another Synthetic", "OwnerId": "owner"})
        result = self.review(account_name="Synthetic Customer")
        self.assertEqual(len(result["accounts"]), 1)
        self.assertEqual(result["accounts"][0]["milestone"]["months"], 12)
        self.assertIsNone(result["window"]["window_start"])
        self.assertEqual(self.row(account_id="account", milestone_months=3)["milestone"]["months"], 3)
        with self.assertRaisesRegex(ValueError, "no --window-start"):
            self.review(account_id="account", window_start=WINDOW_START)
        with self.assertRaisesRegex(ValueError, "named Account"):
            self.review(milestone_months=3)

    def test_on_demand_before_first_milestone_reports_not_due(self):
        self.evidence["opportunities"][0]["CloseDate"] = "2026-09-01"
        milestone = self.row(account_id="account")["milestone"]
        self.assertEqual((milestone["status"], milestone["months"], milestone["date"]), ("not_due", 3, "2026-12-01"))

    def test_renewal_notice_with_no_milestone_and_future_next_window(self):
        self.evidence["opportunities"][0]["CloseDate"] = "2024-01-01"
        row = self.row()
        self.assertEqual(row["milestone"]["status"], "not_due")
        self.assertEqual(row["renewals"][0]["task_due_date"], "2026-10-17")
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = "2027-08-01"
        self.assertEqual(self.review()["accounts"], [])
        self.assertEqual(self.review()["not_due_count"], 1)

    def test_past_notice_in_window_and_missing_end_have_no_task_date(self):
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = "2027-01-01"
        renewal = self.row()["renewals"][0]
        self.assertTrue(renewal["in_review_window"])
        self.assertEqual(renewal["status"], "notice window passed")
        self.assertIsNone(renewal["task_due_date"])
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = None
        self.assertEqual(self.row()["renewals"], [])
        self.assertTrue(any("Subscription End Date" in reason for reason in self.row()["needs_input"]))

    def test_twelfth_month_never_sets_renewal_date(self):
        self.evidence["opportunities"][0]["CloseDate"] = "2025-10-04"
        row = self.row()
        self.assertEqual(row["milestone"]["months"], 12)
        self.assertEqual(row["renewals"][0]["subscription_end_date"], "2027-01-15")
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = None
        self.assertEqual(self.row()["renewals"], [])

    def test_open_opportunity_preserves_assessment_and_routes_actions(self):
        self.evidence["opportunities"].append({"Id": "open", "AccountId": "account", "OwnerId": "another-owner",
                                               "IsClosed": False, "IsWon": False})
        row = self.row()
        self.assertEqual(row["milestone"]["status"], "due")
        self.assertEqual(row["action_route"], "pipeline_hygiene")
        self.assertEqual(row["open_opportunity_ids"], ["open"])

    def test_missing_or_conflicting_org_keeps_independent_renewals_and_null_usage(self):
        for changed in ({"Admin_Organization_UUID__c": None, "Org_UUID__c": None}, {"Org_UUID__c": "wrong"}):
            evidence = copy.deepcopy(self.evidence)
            evidence["accounts"][0].update(changed)
            row = review_customers(evidence, AS_OF, self.policy)["accounts"][0]
            self.assertIsNone(row["usage"])
            self.assertEqual(row["renewals"][0]["task_due_date"], "2026-10-17")
            self.assertTrue(row["needs_input"])

    def test_usage_counts_stay_distinct_and_incomplete_stale_unknown(self):
        usage = self.row()["usage"]
        self.assertEqual((usage["billed_seats"], usage["roster_seats"], usage["active_users"], usage["active_last_seven_days"]), (5, 2, 1, 1))
        for changed in ({"complete": False}, {"complete": "true"}, {"data_through": "2026-10-03"}, {"org_uuid": "wrong"}):
            evidence = copy.deepcopy(self.evidence)
            evidence["usage"]["account"].update(changed)
            self.assertIsNone(review_customers(evidence, AS_OF, self.policy)["accounts"][0]["usage"])
        self.evidence["usage"] = {}
        self.assertIn("usage evidence missing", self.row()["needs_input"])

    def test_usage_ready_includes_trend_mix_and_idle_seats_without_buyer_evidence(self):
        row = self.row()
        self.assertTrue(row["usage_ready"])
        self.assertEqual(row["usage"]["idle_seats"], 1)
        self.assertEqual(row["usage"]["weekly_trend"], self.evidence["usage"]["account"]["weekly_trend"])
        self.assertEqual(row["usage"]["feature_mix"], self.evidence["usage"]["account"]["feature_mix"])
        self.assertNotIn("buyer_evidence", self.evidence)
        self.evidence["buyer_evidence"] = {"account": {"status": "not checked"}}
        self.assertTrue(self.row()["usage_ready"])

    def test_unknown_billed_seats_do_not_hold_complete_usage(self):
        for billed in (None, "missing"):
            with self.subTest(billed=billed):
                evidence = copy.deepcopy(self.evidence)
                if billed == "missing":
                    del evidence["usage"]["account"]["billed_seats"]
                else:
                    evidence["usage"]["account"]["billed_seats"] = billed
                row = review_customers(evidence, AS_OF, self.policy)["accounts"][0]
                self.assertTrue(row["usage_ready"])
                self.assertIsNone(row["usage"]["billed_seats"])
                self.assertEqual(row["needs_input"], [])

    def test_usage_failures_are_not_ready_and_remain_held(self):
        for changed in ({"complete": False}, {"data_through": "2026-10-03"}, {"org_uuid": "wrong"},
                        {"weekly_trend": None}, {"feature_mix": None}, {"weekly_trend": [{}]},
                        {"feature_mix": [{"kind": "mode", "value": "asi", "queries": -1, "users": 1}]}):
            with self.subTest(changed=changed):
                evidence = copy.deepcopy(self.evidence)
                evidence["usage"]["account"].update(changed)
                row = review_customers(evidence, AS_OF, self.policy)["accounts"][0]
                self.assertFalse(row["usage_ready"])
                self.assertIsNone(row["usage"])
                self.assertTrue(row["needs_input"])
        for key in ("weekly_trend", "feature_mix"):
            evidence = copy.deepcopy(self.evidence)
            del evidence["usage"]["account"][key]
            self.assertFalse(review_customers(evidence, AS_OF, self.policy)["accounts"][0]["usage_ready"])

    def test_complete_empty_usage_is_ready_but_not_due_rows_are_not(self):
        self.evidence["usage"]["account"].update(rows=[], weekly_trend=[], feature_mix=[])
        self.assertTrue(self.row()["usage_ready"])
        self.assertEqual(self.row()["usage"]["idle_seats"], 0)
        row = self.row(window_start="2026-10-05T07:00:00-07:00")
        self.assertFalse(row["usage_ready"])

    def test_owned_account_scope_and_complete_native_pages(self):
        self.evidence["accounts"][0]["OwnerId"] = "other-owner"
        self.assertEqual(self.review()["accounts"], [])
        for flag in ("accounts_complete", "opportunities_complete"):
            evidence = copy.deepcopy(self.evidence)
            evidence[flag] = False
            with self.assertRaisesRegex(ValueError, "complete"):
                review_customers(evidence, AS_OF, self.policy)

    def test_duplicate_records_and_nonboolean_salesforce_flags_fail_closed(self):
        for collection in ("accounts", "opportunities"):
            evidence = copy.deepcopy(self.evidence)
            evidence[collection].append(copy.deepcopy(evidence[collection][0]))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                review_customers(evidence, AS_OF, self.policy)
        self.evidence["opportunities"][0]["IsClosed"] = "true"
        with self.assertRaisesRegex(ValueError, "booleans"):
            self.review()

    def test_policy_drives_milestones_type_stage_and_notice(self):
        self.policy["pipeline"]["customer_review"].update(milestone_months=[2, 4], renewal_notice_days=30,
                                                         expansion_type="Reviewed type", expansion_stage="Reviewed stage")
        self.evidence["opportunities"][0]["CloseDate"] = "2026-08-04"
        result = self.review()
        self.assertEqual(result["accounts"][0]["milestone"]["months"], 2)
        self.assertEqual(result["expansion_type"], "Reviewed type")
        self.assertEqual(result["expansion_stage"], "Reviewed stage")
        self.assertEqual(result["accounts"][0]["renewals"][0]["notice_date"], "2026-12-16")
        self.assertEqual(result["writes"], [])

    def test_carried_forward_held_milestone_is_due_again(self):
        row = self.row(window_start="2026-10-04T20:00:00-07:00", carry_forward=[self.receipt_entry()])
        self.assertEqual(row["milestone"]["status"], "due")
        self.assertEqual(self.review(window_start="2026-10-04T20:00:00-07:00", carry_forward=[self.receipt_entry()])["carry_forward_held"], [])

    def test_unresolved_carry_forward_never_dropped_and_resolved_anchor_retries(self):
        held = {"account_id": "account", "milestone_months": None, "milestone_date": None}
        self.assertEqual(self.row(window_start="2026-10-04T20:00:00-07:00", carry_forward=[held])["milestone"]["status"], "due")
        self.evidence["opportunities"][0]["CloseDate"] = None
        result = self.review(carry_forward=[self.receipt_entry()])
        self.assertEqual(result["carry_forward_held"][0]["milestone_date"], "2026-10-04")

    def test_on_demand_reviewed_receipt_suppresses_schedule_but_not_reassessment(self):
        reviewed = [self.receipt_entry(reviewed=True)]
        row = self.row(reviewed=reviewed)
        self.assertEqual(row["milestone"]["status"], "not_due")
        self.assertEqual(row["already_reviewed"], reviewed)
        self.assertEqual(self.row(account_id="account", reviewed=reviewed)["milestone"]["status"], "due")
        wrong = [{**reviewed[0], "milestone_date": "2026-10-03"}]
        self.assertEqual(self.row(reviewed=wrong)["milestone"]["status"], "due")

    def test_run_without_receipt_never_advances_window_start(self):
        first = self.review(window_start=WINDOW_START)
        self.evidence["platform_completed"] = True
        self.evidence["platform_last_run_start"] = AS_OF
        retry = review_customers(self.evidence, "2026-10-06T07:30:00-07:00", self.policy, window_start=WINDOW_START)
        self.assertEqual(first["window"]["window_start"], retry["window"]["window_start"])
        self.assertEqual(retry["accounts"][0]["milestone"]["status"], "due")
        self.assertEqual(self.review()["window"]["window_start"], WINDOW_START)

    def test_malformed_receipts_and_naive_timestamps_stop(self):
        for arguments in ({"carry_forward": {}}, {"reviewed": [self.receipt_entry()]},
                          {"window_start": "2026-09-07T07:30:00"}):
            with self.assertRaises((ValueError, KeyError)):
                self.review(**arguments)
        with self.assertRaisesRegex(ValueError, "offset"):
            review_customers(self.evidence, "2026-10-05T07:30:00", self.policy)

    def test_reviewed_receipts_use_block_as_of_order_and_reject_future_dates(self):
        latest = self.receipt_entry(reviewed=True)
        earlier = {**latest, "receipt_date": "2026-10-04T20:00:00+00:00"}
        self.assertEqual(self.row(reviewed=[latest, earlier])["already_reviewed"], [latest])
        future = {**latest, "receipt_date": "2026-10-06T00:00:00-07:00"}
        with self.assertRaisesRegex(ValueError, "future"):
            self.review(reviewed=[future])

    def test_scheduled_partition_reports_only_actionable_rows_and_counts_unselected_gaps(self):
        self.evidence["accounts"].append({"Id": "old", "Name": "Old Synthetic", "OwnerId": "owner"})
        self.evidence["opportunities"].extend([
            {"Id": "old-won", "AccountId": "old", "IsClosed": True, "IsWon": True, "Deal_Type__c": "New Business",
             "CloseDate": "2020-01-01", "Subscription_Cancel_Date__c": None},
            {"Id": "old-later", "AccountId": "old", "IsClosed": True, "IsWon": True, "Deal_Type__c": "Existing Business",
             "CloseDate": "2021-01-01", "Subscription_Cancel_Date__c": None},
        ])
        result = self.review()
        self.assertEqual([row["account_id"] for row in result["accounts"]], ["account"])
        self.assertEqual(result["not_due_count"], 1)
        self.assertEqual(result["subscription_date_needs_input_count"], 1)
        self.assertNotIn("Old Synthetic", json.dumps(result))
        named = self.review(account_id="old")
        self.assertEqual(named["accounts"][0]["account_id"], "old")
        self.assertEqual(named["not_due_count"], 0)

    def test_suppression_and_unresolved_anchor_are_reported_without_renewal_candidates(self):
        self.evidence["opportunities"][0]["Subscription_Cancel_Date__c"] = "2027-08-01"
        suppressed = self.review(reviewed=[self.receipt_entry(reviewed=True)])
        self.assertEqual(len(suppressed["accounts"]), 1)
        self.assertEqual(suppressed["not_due_count"], 0)
        self.evidence["opportunities"][0]["CloseDate"] = None
        held = self.review()
        self.assertEqual(len(held["accounts"]), 1)
        self.assertIsNone(held["accounts"][0]["anchor"])

    def test_buyer_evidence_starts_at_previous_milestone_in_both_modes(self):
        for anchor, months, expected_start in (("2026-07-04", 3, "2026-07-04"),
                                               ("2026-04-04", 6, "2026-07-04"),
                                               ("2025-10-04", 12, "2026-04-04")):
            with self.subTest(months=months):
                self.evidence["opportunities"][0]["CloseDate"] = anchor
                scheduled = self.row(window_start=WINDOW_START)["milestone"]
                on_demand = self.row(account_id="account")["milestone"]
                self.assertEqual(scheduled["months"], months)
                self.assertEqual(scheduled["evidence_window"], {"start": expected_start, "as_of": AS_OF})
                self.assertEqual(on_demand["evidence_window"], scheduled["evidence_window"])

    def test_on_demand_as_of_suppresses_review_but_never_advances_scheduled_window(self):
        on_demand_as_of = "2026-10-04T15:00:00-07:00"
        self.evidence["usage"]["account"]["data_through"] = "2026-10-03"
        run = review_customers(self.evidence, on_demand_as_of, self.policy, account_id="account")
        self.assertIsNone(run["window"]["window_start"])
        entry = {**self.receipt_entry(), "receipt_date": run["window"]["as_of"]}
        scheduled = self.review(reviewed=[entry])
        self.assertEqual(scheduled["window"]["window_start"], WINDOW_START)
        self.assertEqual(scheduled["accounts"][0]["already_reviewed"][0]["receipt_date"], on_demand_as_of)

    def test_cli_receipt_lists_and_read_only_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            held = Path(directory) / "held.json"
            reviewed = Path(directory) / "reviewed.json"
            path.write_text(json.dumps(self.evidence))
            held.write_text(json.dumps([self.receipt_entry()]))
            reviewed.write_text("[]")
            before = path.read_bytes()
            command = [sys.executable, str(WORKFLOW / "scripts/customer_review.py"), "--input", str(path), "--as-of", AS_OF,
                       "--window-start", "2026-10-04T20:00:00-07:00", "--carry-forward", str(held), "--reviewed", str(reviewed)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["accounts"][0]["milestone"]["status"], "due")
            self.assertEqual(json.loads(result.stdout)["writes"], [])
            self.assertEqual(path.read_bytes(), before)


class CustomerContractTests(unittest.TestCase):
    def test_exact_policy_block_and_registry_key(self):
        text = (ROOT / "_core/policy.yaml").read_text()
        exact = '''  customer_review:                 # Closed Won customer milestone reviews and renewal notices. Not ARR growth
    schedule: {days: [MO], week_of_month: 1, time: "07:30", tz: America/Los_Angeles}
    milestone_months: [3, 6, 12]   # calendar months after the customer's first verified non-trial Closed Won
    renewal_notice_days: 90        # renewal Task this many days before the subscription end date
    expansion_type: Existing Business
    expansion_stage: S1
'''
        self.assertIn(exact, text)
        policy = yaml.safe_load(text)
        self.assertEqual(set(policy["pipeline"]["customer_review"]), {"schedule", "milestone_months", "renewal_notice_days", "expansion_type", "expansion_stage"})
        self.assertEqual(policy["tooling"]["scripts"]["customer_review"], "workspaces/pipeline/workflows/customer-review/scripts/customer_review.py")
        self.assertNotIn("expansion", policy["pipeline"])
        self.assertNotIn("expansion_review", policy["tooling"]["scripts"])

    def test_routes_and_retired_paths_absent(self):
        self.assertFalse((WORKFLOW.parent / "expansion-review").exists())
        self.assertFalse((WORKFLOW / "scripts/expansion_review.py").exists())
        self.assertFalse((ROOT / "_core/tests/test_expansion_review.py").exists())
        for path in ROOT.rglob("*.md"):
            self.assertNotIn("expansion-review", path.read_text(), str(path))
        self.assertIn("`customer-review`", (ROOT / "AGENTS.md").read_text())

    def test_window_boundary_is_data_not_a_since_clock(self):
        helper = (WORKFLOW / "scripts/customer_review.py").read_text()
        self.assertNotIn("--since", helper)
        self.assertIn('parser.add_argument("--window-start")', helper)
        self.assertIn('parser.add_argument("--as-of", required=True)', helper)
        reference = (WORKFLOW / "references/proposals.md").read_text()
        self.assertIn('"window_start": "<ISO with offset>"', reference)
        self.assertNotIn('"since":', reference)

    def test_contract_receipts_and_gates_preserved(self):
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        for phrase in ("rules#approval", "rules#write_protocol", "rules#scheduled_runs", "numbered", "native readback",
                       "No reply writes nothing", "Account.OwnerId", "customer_review_receipt", "platform completed flag",
                       "On-demand runs in Pipeline", "Held includes unreadable usage", "Anchor", "Window and milestone", "Renewal"):
            self.assertIn(phrase, contract)
        self.assertNotIn("workflows/pilot-usage/", contract)
        self.assertLessEqual(len(contract.splitlines()), 80)
        for reference in (WORKFLOW / "references").glob("*.md"):
            self.assertLessEqual(len(reference.read_text().splitlines()), 200)

    def test_shared_queries_and_milestone_assessment_content(self):
        for workflow in (WORKFLOW, ROOT / "workspaces/pipeline/workflows/pilot-usage"):
            self.assertIn("workspaces/pipeline/references/pilot-usage-queries.md", (workflow / "CONTEXT.md").read_text())
        reference = (WORKFLOW / "references/proposals.md").read_text()
        for phrase in ("3 months, Adoption", "6 months, Value and growth", "12 months, Account health",
                       "not demand inference", "native", "not ready proposals", "notice window passed", "fresh duplicate",
                       "required fields", "No pre-approval", "current Pacific date after approval", "not helper selection",
                       "No receipt block means not reviewed", "Only mark earlier catch-up milestones superseded"):
            self.assertIn(phrase, reference)

    def test_report_scope_evidence_bounds_and_receipt_clock_are_explicit(self):
        reference = (WORKFLOW / "references/proposals.md").read_text()
        collect = (WORKFLOW / "references/collect.md").read_text()
        self.assertNotIn("lists every qualifying Account", reference)
        self.assertIn("Every other owned customer is not_due_count only", reference)
        self.assertIn("one subscription_date_needs_input_count", reference)
        self.assertIn("previous milestone date, or the anchor for the first milestone, through as_of in both modes", reference)
        self.assertIn("omits window_start, but includes as_of", reference)
        self.assertIn("receipt_date from that block's as_of", reference)
        self.assertIn("An on-demand as_of never advances that boundary", collect)
        self.assertNotIn("native receipt message timestamp", collect)

    def test_usage_completion_and_optional_buyer_context_gates(self):
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        collect = (WORKFLOW / "references/collect.md").read_text()
        proposals = (WORKFLOW / "references/proposals.md").read_text()
        for text in (contract, collect, proposals):
            self.assertNotIn("missing evidence holds the assessment", text)
            self.assertNotIn("Held includes incomplete, missing evidence", text)
            self.assertIn("usage_ready", text)
        self.assertIn("Reviewed requires usage_ready true and the assessment shown", proposals)
        self.assertIn("unknown billed seats never hold", proposals)
        self.assertIn("Buyer evidence is optional context and never holds", collect)
        self.assertIn('"no recent buyer contact since <date>" with the dates searched', collect)
        self.assertIn('"not checked"', proposals)
        self.assertIn("Expansion Opportunity proposals still require buyer evidence", proposals)
        self.assertIn("numbered follow-ups drawn from usage facts and cite the numbers", proposals)
        self.assertIn("Add no fixed numeric threshold", proposals)
        self.assertIn("No Gmail drafts or outreach", proposals)


if __name__ == "__main__":
    unittest.main()
