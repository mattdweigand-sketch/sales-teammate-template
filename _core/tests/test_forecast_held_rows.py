"""Spec E. A failed reviewed eligibility predicate holds the row, completes the run incomplete, and withholds D.

Synthetic deals only. Operator's typed override is reviewed run input, never helper authentication.
"""
import copy
import json
import unittest
from pathlib import Path

import yaml

from test_forecast_deck import fixture_inputs, presentation
import forecast_deck
from forecast_math import HOLD_PREDICATES, OPERATOR_CALL_LABEL, calculate
from forecast_notify import build_payload

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workspaces/forecasting/workflows/forecast-weekly"
URL = "https://example.test/run"
COVERAGE = {"ready": True, "process_status": "complete", "affected": []}
BUCKET_SUMS = ("commit", "upside", "call", "gap", "buffer", "path_shortfall")


class HeldRowTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.policy["forecast"]["targets"] = {"2026-Q1": 0, "2026-Q2": 0, "2026-Q3": 333333, "2026-Q4": 650000}
        self.policy["forecast"]["target_default"] = 1000000
        self.policy["forecast"]["deck"]["presentation_id"] = "fictional-deck"
        self.reviewed, self.deck = fixture_inputs(1, 1, 1)
        self.commit, self.upside = self.reviewed["deals"]
        self.baseline = calculate(self.reviewed, self.policy)
        self.assertEqual((self.baseline["status"], self.baseline["held"], self.baseline["operator_calls"]), ("complete", [], []))

    def hold_commit(self, data):
        data["deals"][0]["blockers"] = [{"description": "Signing approval", "owner": None,
                                         "date": None, "evidence": "synthetic-email"}]
        return "commit_blocker_owner_date"

    def hold_upside(self, data):
        data["deals"][1].update(buyer_delay_date="2027-01-15", buyer_delay_evidence="synthetic-email")
        return "buyer_delay_past_quarter_end"

    def test_held_commit_row_leaves_every_bucket_sum_and_keeps_qualified_pipeline(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_commit(data)
        result = calculate(data, self.policy)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual({key: result[key] for key in BUCKET_SUMS},
                         {"commit": "0", "upside": "30000", "call": "50000.50", "gap": "599999.50",
                          "buffer": "0", "path_shortfall": "569999.50"})
        self.assertEqual([row["Id"] for row in result["path_to_target"]], [self.upside["Id"]])
        self.assertEqual(result["booked"], self.baseline["booked"])
        self.assertEqual(result["qualified_pipeline"], self.baseline["qualified_pipeline"])
        self.assertEqual(result["qualified_pipeline"], "80000")
        (held,) = result["held"]
        self.assertEqual((held["Id"], held["failed_predicate"], held["held_amount"], held["hold"]),
                         (self.commit["Id"], predicate, "50000", HOLD_PREDICATES[predicate]))
        for key, value in data["deals"][0].items():
            self.assertEqual(held[key], value, key)
        self.assertNotIn("unmatched_operator_call", held)
        self.assertEqual(result["operator_calls"], [])

    def test_held_upside_row_leaves_every_bucket_sum_and_keeps_qualified_pipeline(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_upside(data)
        result = calculate(data, self.policy)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual({key: result[key] for key in BUCKET_SUMS},
                         {"commit": "50000", "upside": "0", "call": "100000.50", "gap": "549999.50",
                          "buffer": "0", "path_shortfall": "549999.50"})
        self.assertEqual(result["path_to_target"], [])
        self.assertEqual(result["qualified_pipeline"], "80000")
        self.assertEqual([(row["Id"], row["failed_predicate"], row["held_amount"]) for row in result["held"]],
                         [(self.upside["Id"], predicate, "30000")])

    def test_each_held_row_appears_once_and_pull_ins_stay_separate(self):
        data = copy.deepcopy(self.reviewed)
        self.hold_commit(data)
        self.hold_upside(data)
        result = calculate(data, self.policy)
        self.assertEqual(sorted(row["Id"] for row in result["held"]), sorted([self.commit["Id"], self.upside["Id"]]))
        self.assertEqual(len(result["held"]), 2)
        self.assertEqual((result["commit"], result["upside"], result["call"]), ("0", "0", "50000.50"))
        self.assertEqual(result["pull_ins"], self.baseline["pull_ins"])

    def test_incomplete_status_never_titles_the_notification_ready(self):
        coverage = json.dumps({"ready": True, "process_status": "complete", "lines": ["Coverage ready."]})
        payload = build_payload(0, coverage, "Booked $1.", URL, None, "incomplete")
        self.assertEqual(payload["title"], "Weekly forecast incomplete")
        self.assertIn("Workflow status: incomplete", payload["body"])
        self.assertEqual(build_payload(0, coverage, "", URL, None, "ready")["title"], "Weekly forecast ready")

    def test_d_is_withheld_while_any_hold_remains(self):
        for hold in (self.hold_commit, self.hold_upside):
            data = copy.deepcopy(self.reviewed)
            hold(data)
            result = calculate(data, self.policy)
            with self.subTest(hold=hold.__name__), self.assertRaisesRegex(ValueError, "held: D is not proposed"):
                forecast_deck.plan(presentation(), result, data, self.deck, self.policy, coverage=COVERAGE)

    def override(self, data, deal, bucket, predicate, approved_turn="forecast-thread-turn-synthetic-1"):
        data["operator_call"] = [{"deal": deal, "bucket": bucket, "predicate": predicate,
                              "reason": "Buyer confirmed signature timing on the call.",
                              "approved_turn": approved_turn}]

    def test_override_of_one_predicate_leaves_a_row_that_also_fails_another_held(self):
        """RP-01. A delay-only override never clears a commit row that also has an unowned blocker."""
        data = copy.deepcopy(self.reviewed)
        blocker_predicate = self.hold_commit(data)
        data["deals"][0].update(buyer_delay_date="2027-01-15", buyer_delay_evidence="synthetic-email")
        both = calculate(data, self.policy)
        self.override(data, self.commit["Id"], "commit", "buyer_delay_past_quarter_end")
        result = calculate(data, self.policy)
        self.assertEqual((result["status"], result["commit"], [row["Id"] for row in result["held"]]),
                         ("incomplete", "0", [self.commit["Id"]]))
        self.assertEqual(result["operator_calls"], [])
        self.assertEqual(both["held"][0]["failed_predicates"], ["buyer_delay_past_quarter_end", blocker_predicate])
        self.assertEqual(both["held"][0]["failed_predicate"], "buyer_delay_past_quarter_end")
        (held,) = result["held"]
        self.assertEqual((held["Id"], held["failed_predicate"], held["failed_predicates"], held["held_amount"]),
                         (self.commit["Id"], blocker_predicate, [blocker_predicate], "50000"))
        self.assertEqual(held["operator_call"], data["operator_call"][0])
        self.assertNotIn("unmatched_operator_call", held)
        self.assertEqual({key: result[key] for key in BUCKET_SUMS},
                         {"commit": "0", "upside": "30000", "call": "50000.50", "gap": "599999.50",
                          "buffer": "0", "path_shortfall": "569999.50"})
        self.assertEqual(result["qualified_pipeline"], "80000")
        with self.assertRaisesRegex(ValueError, "held: D is not proposed"):
            forecast_deck.plan(presentation(), result, data, self.deck, self.policy, coverage=COVERAGE)
        data["operator_call"].append({**data["operator_call"][0], "predicate": blocker_predicate})
        with self.assertRaisesRegex(ValueError, "operator_call"):
            calculate(data, self.policy)
        data["operator_call"] = [{**data["operator_call"][0], "predicate": blocker_predicate}]
        self.assertEqual([row["Id"] for row in calculate(data, self.policy)["held"]], [self.commit["Id"]])

    def test_valid_scoped_override_counts_once_and_is_labeled_in_report_and_d_preview(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_commit(data)
        self.override(data, self.commit["Id"], "commit", predicate)
        result = calculate(data, self.policy)
        self.assertEqual((result["status"], result["held"]), ("complete", []))
        for key in BUCKET_SUMS + ("booked", "qualified_pipeline", "path_to_target", "pull_ins"):
            self.assertEqual(result[key], self.baseline[key], key)
        (call,) = result["operator_calls"]
        self.assertEqual((call["Id"], call["bucket"], call["label"], call["failed_predicate"]),
                         (self.commit["Id"], "commit", OPERATOR_CALL_LABEL, predicate))
        self.assertEqual(call["operator_call"], data["operator_call"][0])
        self.assertEqual(call[self.policy["forecast"]["amount_field"]], "50000")
        planned = forecast_deck.plan(presentation(), result, data, self.deck, self.policy, coverage=COVERAGE)
        self.assertEqual(planned["operator_calls"], [{
            "Id": self.commit["Id"], "Name": self.commit["Name"], "bucket": "commit", "label": "Operator's call",
            "failed_predicate": predicate, "approved_turn": "forecast-thread-turn-synthetic-1"}])
        self.assertEqual(self.field(planned, "CORE[1][1]"), self.commit["Name"])
        self.assertEqual(self.field(planned, "Q4 CALL"), "$100,001")
        changed = copy.deepcopy(data)
        changed["operator_call"][0]["approved_turn"] = "forecast-thread-turn-synthetic-2"
        fresh = forecast_deck.plan(presentation(), calculate(changed, self.policy), changed, self.deck, self.policy,
                                   coverage=COVERAGE)
        with self.assertRaisesRegex(ValueError, "Operator's call labels changed since the D preview"):
            forecast_deck.check_approved(fresh, planned)

    def field(self, planned, label):
        return next(entry["new"] for entry in planned["fields"] if entry["label"] == label)

    def test_missing_or_out_of_scope_override_stays_held(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_commit(data)
        cases = {
            "missing": lambda d: None,
            "other_deal": lambda d: self.override(d, self.upside["Id"], "upside", "buyer_delay_past_quarter_end"),
            "other_predicate": lambda d: self.override(d, self.commit["Id"], "commit", "buyer_delay_past_quarter_end"),
            "other_bucket": lambda d: self.override(d, self.commit["Id"], "upside", predicate),
        }
        for name, arrange in cases.items():
            case = copy.deepcopy(data)
            arrange(case)
            with self.subTest(case=name):
                result = calculate(case, self.policy)
                self.assertEqual(result["status"], "incomplete")
                self.assertEqual([row["Id"] for row in result["held"]], [self.commit["Id"]])
                self.assertEqual(result["operator_calls"], [])
                self.assertEqual(result["commit"], "0")
                if name in ("other_predicate", "other_bucket"):
                    self.assertEqual(result["held"][0]["unmatched_operator_call"], case["operator_call"][0])
                with self.assertRaisesRegex(ValueError, "held: D is not proposed"):
                    forecast_deck.plan(presentation(), result, case, self.deck, self.policy, coverage=COVERAGE)

    def test_malformed_override_identity_and_scope_checks_still_raise(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_commit(data)
        valid = {"deal": self.commit["Id"], "bucket": "commit", "predicate": predicate,
                 "reason": "Buyer confirmed timing.", "approved_turn": "forecast-thread-turn-synthetic-1"}
        invalid = [{"operator_call": "approved"}, {"operator_call": [None]}, {"operator_call": [{}]},
                   {"operator_call": [{**valid, "extra": True}]}, {"operator_call": [valid, valid]}]
        invalid += [{"operator_call": [{key: value for key, value in valid.items() if key != missing}]} for missing in valid]
        invalid += [{"operator_call": [{**valid, key: value}]} for key, value in
                    (("deal", ""), ("deal", "fixture-won"), ("deal", "fixture-pull-00"), ("deal", "unknown"),
                     ("bucket", "excluded"), ("predicate", "stage"), ("reason", " "), ("approved_turn", None))]
        for case in invalid:
            changed = {**copy.deepcopy(data), **case}
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, "operator_call"):
                calculate(changed, self.policy)

    def test_override_does_not_bypass_amount_structure_or_other_predicates(self):
        data = copy.deepcopy(self.reviewed)
        predicate = self.hold_commit(data)
        self.override(data, self.commit["Id"], "commit", predicate)
        for change, message in ((lambda row: row.update(ARR__c=None), "ARR__c"),
                                (lambda row: row.update(StageName="S2"), "commit requires"),
                                (lambda row: row.update(last_activity_date="2026-01-01"), "activity_days"),
                                (lambda row: row.__delitem__("blockers"), "needs-input"),
                                (lambda row: row["blockers"].append("not-reviewed"), "needs-input")):
            changed = copy.deepcopy(data)
            change(changed["deals"][0])
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                calculate(changed, self.policy)

    def test_structural_errors_do_not_become_held_rows(self):
        for change, message in ((lambda d: d["deals"][0].__delitem__("buyer_delay_date"), "needs-input"),
                                (lambda d: d["deals"][0].update(buyer_delay_date="2027-01-15"), "needs source evidence"),
                                (lambda d: d["deals"][0].update(blockers="none"), "needs-input"),
                                (lambda d: d["deals"][0].update(StageName="Closed Won"), "StageName"),
                                (lambda d: d["deals"][1].update(ARR__c="abc"), "ARR__c"),
                                (lambda d: d["pull_ins"][0].update(CloseDate="2026-12-01"), "next quarter"),
                                (lambda d: d.update(quarter="2026-4"), "quarter")):
            data = copy.deepcopy(self.reviewed)
            change(data)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                calculate(data, self.policy)

    def test_references_label_held_rows_and_matts_call(self):
        compute = (WORKFLOW / "references/compute.md").read_text()
        report = (WORKFLOW / "references/report-format.md").read_text()
        deck = (WORKFLOW / "references/deck.md").read_text()
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        for text in ("`status` is `incomplete`", "`held`", "`operator_call`", "`approved_turn`", "Operator's call"):
            self.assertIn(text, compute)
        for text in ("## Held (<n>)", "Subtotals incomplete", "Operator's call", "approved_turn"):
            self.assertIn(text, report)
        self.assertIn("D is not proposed while any row is held", deck)
        self.assertIn("Operator's call", deck)
        self.assertIn("forecast_notify", "\n".join(line for line in contract.splitlines() if line.startswith("7. ")))
        self.assertIn("incomplete while any row is held", contract)
        self.assertLessEqual(len(contract.splitlines()), 80)
        # RP-02. The workflow maps the math status onto the notify enum, never passes `complete` through.
        self.assertIn("--process-status <status>`", contract)
        self.assertIn("Status is `ready` when step 5 returned `complete` and step 6 exited 0, `incomplete` when any row is held, "
                      "otherwise `review-needed` when step 6 exited 1.", contract)
        self.assertNotIn("--process-status <step 5 status>", contract)
        # RP-03, RP-04, OP-05 static pins.
        self.assertIn("Every in-quarter deal not under Calling or Held, one line each", report)
        helper_row = next(line for line in contract.splitlines() if line.startswith("| Helper |"))
        for name in ("`forecast_deck`", "`coverage_check`", "`hygiene_check`", "`gmail_digest`"):
            self.assertIn(name, helper_row.split("|")[3])
        self.assertIn("forecast only, `forecast_deck`, `coverage_check`, `hygiene_check`, `gmail_digest`", helper_row)
        tracking = (WORKFLOW / "references/tracking.md").read_text()
        gate = tracking.split("## Notification gate", 1)[1].split("## ", 1)[0]
        self.assertNotIn("--since", gate)
        interfaces = (ROOT / "_core/scripts/interfaces.md").read_text()
        self.assertIn("`--since` required for weekly, ignored for tracking", interfaces)


if __name__ == "__main__":
    unittest.main()
