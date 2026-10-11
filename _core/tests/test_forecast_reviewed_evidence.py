"""Approved forecast delay, blocker, saved-coverage and rollover boundaries."""
import copy
from datetime import date, timedelta
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from test_forecast_deck import fixture_inputs, presentation
import forecast_deck
from forecast_math import calculate

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workspaces/forecasting/workflows/forecast-weekly"


class ForecastReviewedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.policy["forecast"]["targets"] = {"2026-Q1": 0, "2026-Q2": 0, "2026-Q3": 333333, "2026-Q4": 650000}
        self.policy["forecast"]["target_default"] = 1000000
        self.policy["forecast"]["deck"]["presentation_id"] = "fictional-deck"
        self.reviewed, self.deck = fixture_inputs(1, 1, 1)
        for row in self.reviewed["deals"]:
            row.update(buyer_delay_date=None, buyer_delay_evidence=None, blockers=[])
        self.coverage = {"ready": True, "process_status": "complete", "affected": []}

    def plan(self, coverage):
        return forecast_deck.plan(presentation(), calculate(self.reviewed, self.policy),
                                  self.reviewed, self.deck, self.policy, coverage=coverage)

    def test_missing_review_is_needs_input_for_each_current_quarter_bucket(self):
        for bucket in ("commit", "upside", "excluded"):
            for key in ("buyer_delay_date", "buyer_delay_evidence", "blockers"):
                data = copy.deepcopy(self.reviewed)
                row = data["deals"][0]
                row["bucket"] = bucket
                del row[key]
                with self.subTest(bucket=bucket, key=key), self.assertRaisesRegex(ValueError, "needs-input.*" + key):
                    calculate(data, self.policy)

    def test_buyer_delay_quarter_boundary_for_commit_upside_and_excluded(self):
        for bucket in ("commit", "upside", "excluded"):
            for delay in ("2026-12-31", "2027-01-01"):
                data = copy.deepcopy(self.reviewed)
                row = data["deals"][0]
                row.update(bucket=bucket, buyer_delay_date=delay, buyer_delay_evidence="synthetic-email")
                with self.subTest(bucket=bucket, delay=delay):
                    result = calculate(data, self.policy)
                    if delay == "2027-01-01" and bucket != "excluded":
                        self.assertEqual(result["status"], "incomplete")
                        self.assertEqual([(r["Id"], r["failed_predicate"]) for r in result["held"]],
                                         [(row["Id"], "buyer_delay_past_quarter_end")])
                    else:
                        self.assertEqual((result["status"], result["held"]), ("complete", []))

    def test_future_activity_is_next_meeting_evidence_never_last_activity(self):
        """W7. Helper and collect.md agree. Latest activity is on or before as-of, an upcoming meeting is separate evidence."""
        data = copy.deepcopy(self.reviewed)
        as_of = date.fromisoformat(data["as_of"])
        data["deals"][0]["last_activity_date"] = (as_of + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "last_activity_date must be within forecast.activity_days of as_of"):
            calculate(data, self.policy)
        data["deals"][0]["last_activity_date"] = as_of.isoformat()
        calculate(data, self.policy)
        collect = (WORKFLOW / "references/collect.md").read_text()
        self.assertIn("Latest activity is the newest held meeting or buyer message on or before as-of and feeds `last_activity_date`.", collect)
        self.assertIn("An accepted upcoming meeting is next-meeting evidence in the packet, never `last_activity_date`.", collect)

    def test_delay_structure_and_evidence_fail_closed(self):
        for value, evidence in (("not-a-date", "source"), (False, "source"),
                                ("2027-01-01", None), ("2027-01-01", ""), (None, False)):
            data = copy.deepcopy(self.reviewed)
            data["deals"][0].update(buyer_delay_date=value, buyer_delay_evidence=evidence)
            with self.subTest(value=value, evidence=evidence), self.assertRaisesRegex(ValueError, "needs-input"):
                calculate(data, self.policy)

    def test_commit_needs_owner_and_date_for_each_reviewed_open_blocker(self):
        for owner, deadline in ((None, "2026-11-01"), ("Synthetic Buyer", None), (None, None)):
            data = copy.deepcopy(self.reviewed)
            row = data["deals"][0]
            row["blockers"] = [{"description": "Signing approval", "owner": owner,
                                "date": deadline, "evidence": "synthetic-email"}]
            with self.subTest(owner=owner, deadline=deadline):
                result = calculate(data, self.policy)
                self.assertEqual(result["status"], "incomplete")
                self.assertEqual([(r["Id"], r["failed_predicate"], r["hold"]) for r in result["held"]],
                                 [(row["Id"], "commit_blocker_owner_date", "commit blocker needs a named owner and date")])
            row["bucket"] = "upside"
            self.assertEqual(calculate(data, self.policy)["held"], [])

    def test_blocker_schema_is_checked_even_for_upside(self):
        valid = {"description": "Signing approval", "owner": "Synthetic Buyer",
                 "date": "2026-11-01", "evidence": "synthetic-email"}
        invalid = [None, {}, "not-reviewed", [None]]
        invalid += [[{key: value for key, value in valid.items() if key != missing}]
                    for missing in valid]
        invalid += [[{**valid, key: value}] for key, value in
                    (("description", ""), ("owner", ""), ("owner", False),
                     ("date", "not-a-date"), ("evidence", ""), ("evidence", False))]
        for blockers in invalid:
            data = copy.deepcopy(self.reviewed)
            data["deals"][1]["blockers"] = blockers
            with self.subTest(blockers=blockers), self.assertRaisesRegex(ValueError, "needs-input"):
                calculate(data, self.policy)

    def test_owned_dated_blockers_keep_totals_and_all_allowed_activity(self):
        expected = calculate(self.reviewed, self.policy)
        self.reviewed["deals"][0]["blockers"] = [
            {"description": "Signing approval", "owner": "Synthetic Buyer",
             "date": "2026-11-01", "evidence": "synthetic-email"}]
        self.assertEqual(calculate(self.reviewed, self.policy), expected)

    def test_saved_coverage_is_required_and_not_ready_never_plans_d(self):
        with self.assertRaisesRegex(ValueError, "coverage"):
            forecast_deck.plan(presentation(), calculate(self.reviewed, self.policy),
                               self.reviewed, self.deck, self.policy)
        for coverage in (None, {}, {"ready": False, "process_status": "complete", "affected": []},
                         {"ready": "true", "process_status": "complete", "affected": []},
                         {"ready": True, "process_status": "incomplete", "affected": []},
                         {**self.coverage, "affected": None}, {**self.coverage, "affected": "unknown"},
                         {**self.coverage, "affected": [None]}):
            with self.subTest(coverage=coverage), self.assertRaisesRegex(ValueError, "coverage"):
                self.plan(coverage)

    def test_affected_booked_commit_upside_pullin_and_excluded_pipeline_withhold_d(self):
        excluded = copy.deepcopy(self.reviewed["deals"][0])
        excluded.update(Id="excluded-qualified", bucket="excluded")
        self.reviewed["deals"].append(excluded)
        ids = [row["Id"] for group in ("booked", "deals", "pull_ins") for row in self.reviewed[group]]
        for identity in ids:
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "coverage.*" + identity):
                self.plan({**self.coverage, "affected": [identity]})
        self.plan(self.coverage)

    def test_noncontributing_excluded_rows_do_not_expand_the_affected_gate(self):
        excluded = copy.deepcopy(self.reviewed["deals"][0])
        excluded.update(Id="excluded-early", bucket="excluded", StageName="S1")
        self.reviewed["deals"].append(excluded)
        self.plan({**self.coverage, "affected": [excluded["Id"]]})

    def test_replan_rechecks_saved_coverage_before_reusing_d(self):
        approved = self.plan(self.coverage)
        for coverage in ({**self.coverage, "ready": False}, {**self.coverage, "affected": None},
                         {**self.coverage, "affected": [self.reviewed["deals"][0]["Id"]]}):
            with self.subTest(coverage=coverage), self.assertRaisesRegex(ValueError, "coverage"):
                forecast_deck.check_approved(self.plan(coverage), approved)

    def test_cli_replan_refuses_changed_coverage_without_emitting_a_write_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            values = {"presentation": presentation(), "forecast": calculate(self.reviewed, self.policy),
                      "reviewed": self.reviewed, "input": self.deck, "coverage": self.coverage,
                      "approved": self.plan(self.coverage)}
            policy_path = directory / "policy.yaml"
            policy_path.write_text(yaml.safe_dump(self.policy))
            arguments = ["plan", "--policy", str(policy_path)]
            for key, value in values.items():
                path = directory / f"{key}.json"
                path.write_text(json.dumps(value))
                arguments.extend(("--" + key, str(path)))
            (directory / "coverage.json").write_text(json.dumps({**self.coverage, "ready": False}))
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(forecast_deck.main(arguments), 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("coverage", error.getvalue())

    def test_rollover_review_routes_before_unchanged_suppression_and_retries_partial(self):
        learning = (WORKFLOW / "references/learning.md").read_text()
        tracking = (WORKFLOW / "references/tracking.md").read_text()
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        for text in ("first scheduled tracking run after a calendar-quarter rollover",
                     "prior quarter's review receipt", "complete or partial status",
                     "remains due on the next scheduled tracking run"):
            self.assertIn(text, learning)
        self.assertIn("Before an unchanged scheduled run is suppressed", tracking)
        self.assertIn("no rollover-review output", tracking)
        self.assertIn("scheduled tracking runs check rollover receipts", contract.lower())
        self.assertNotIn("At quarter end, propose criteria edits", contract)
        self.assertLessEqual(len(contract.splitlines()), 80)


if __name__ == "__main__":
    unittest.main()
