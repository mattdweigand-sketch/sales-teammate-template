"""Forward-quarter creation pace, approved write scope and Monday notify behavior."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workspaces/forecasting/workflows/forecast-weekly"
sys.path.insert(0, str(WORKFLOW / "scripts"))
from forecast_math import calculate_tracking
from forecast_notify import main, tracking_decision


class ForwardTrackingTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.data = {"as_of": "2026-06-15", "records": [], "reads_complete": True}

    def row(self, identity, amount, close="2026-09-30", created="2026-06-09T12:00:00Z", won=False):
        return {"Id": identity, "ARR__c": amount, "Amount": 999999, "CloseDate": close,
                "CreatedDate": created, "IsClosed": won, "IsWon": won, "ForecastCategoryName": "Pipeline"}

    def test_ramp_quarters_and_empty_pipeline_have_real_creation_needs(self):
        result = calculate_tracking(self.data, self.policy)
        first, second = result["forward_quarters"]
        self.assertEqual((first["period"], first["target"], first["coverage"]), ("2026-Q3", "250000.00", "0.0000"))
        self.assertEqual((first["coverage_shortfall"], first["days_until_start"], first["required_created_arr_per_week"]),
                         ("750000.00", 16, "328125.00"))
        self.assertEqual((second["period"], second["target"], second["coverage"]), ("2026-Q4", "250000.00", "0.0000"))
        self.assertTrue(first["coverage_alert"])
        self.assertTrue(result["created_arr"]["below_required"])

    def test_cross_year_forward_scope_and_default_target(self):
        self.data["as_of"] = "2026-12-28"
        self.data["records"] = [self.row("future", 3000000, close="2027-03-31", created="2026-12-27T12:00:00Z")]
        result = calculate_tracking(self.data, self.policy)
        self.assertEqual([row["period"] for row in result["forward_quarters"]], ["2027-Q1", "2027-Q2"])
        self.assertEqual(result["forward_quarters"][0]["coverage"], "12.0000")
        self.assertEqual(result["forward_quarters"][0]["required_created_arr_per_week"], "0.00")

    def test_created_arr_uses_local_created_date_not_close_date_or_status(self):
        self.data["records"] = [self.row("included", 100, close="2028-03-31", won=True),
                                self.row("boundary", 200, created="2026-06-09T07:00:00Z"),
                                self.row("before", 999, created="2026-06-09T06:59:59Z")]
        created = calculate_tracking(self.data, self.policy)["created_arr"]
        self.assertEqual((created["start"], created["end"], created["amount"]), ("2026-06-09", "2026-06-15", "300.00"))
        self.assertEqual(created["opportunity_ids"], ["boundary", "included"])

    def test_zero_target_and_covered_target_have_no_creation_shortfall(self):
        self.policy["forecast"]["targets"]["2026-Q3"] = 0
        self.data["records"] = [self.row("won", 700000, close="2026-12-31", won=True)]
        result = calculate_tracking(self.data, self.policy)
        self.assertEqual([row["coverage"] for row in result["forward_quarters"]], [None, None])
        self.assertEqual(result["created_arr"]["required_per_week"], "0.00")
        self.assertFalse(result["created_arr"]["below_required"])

    def test_missing_or_future_creation_evidence_and_missing_arr_fail(self):
        for created in (None, "2026-06-09", "2026-06-16T12:00:00Z"):
            self.data["records"] = [self.row("bad", 100, created=created)]
            with self.subTest(created=created), self.assertRaises((ValueError, TypeError)):
                calculate_tracking(self.data, self.policy)
        self.data["records"] = [self.row("bad", None)]
        with self.assertRaises(ValueError):
            calculate_tracking(self.data, self.policy)

    def test_created_arr_window_expiry_is_material_without_record_change(self):
        self.data["records"] = [self.row("recent", 100)]
        previous = calculate_tracking(self.data, self.policy)["snapshot"]
        current = {**self.data, "as_of": "2026-06-16", "previous": previous}
        self.assertTrue(calculate_tracking(current, self.policy)["material_change"])
        self.assertEqual(calculate_tracking(current, self.policy)["created_arr"]["amount"], "0.00")

    def test_old_snapshot_initializes_forward_target_baseline(self):
        previous = calculate_tracking(self.data, self.policy)["snapshot"]
        del previous["forward_targets"]
        self.assertTrue(calculate_tracking({**self.data, "previous": previous}, self.policy)["material_change"])

    def test_monday_gate_silences_only_complete_ready_unchanged_runs(self):
        previous = calculate_tracking(self.data, self.policy)["snapshot"]
        current = {**self.data, "previous": previous}
        self.assertEqual(tracking_decision(current, self.policy, "pace", "run"), {"notify": False, "payload": None})
        for changed in ({**current, "reads_complete": False}, {**current, "reads_complete": "true"}):
            decision = tracking_decision(changed, self.policy, "pace", "run")
            self.assertTrue(decision["notify"])
            self.assertEqual(decision["payload"]["title"], "Monday pace report incomplete")
        self.assertTrue(tracking_decision(current, self.policy, "pace", "run", "review-needed")["notify"])

    def test_notification_cli_needs_no_forecast_gmail_or_calendar_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tracking.json"
            path.write_text(json.dumps(self.data))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--tracking-input", str(path), "--since", "2026-06-15T07:00:00-07:00",
                                       "--thread-url", "https://example.test/run"]), 0)
            decision = json.loads(output.getvalue())
            self.assertTrue(decision["notify"])
            self.assertEqual(decision["payload"]["title"], "Monday pace report ready")
            path.write_text("{}")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--tracking-input", str(path), "--since", "date", "--thread-url", "run"]), 0)
            self.assertEqual(json.loads(output.getvalue())["payload"]["title"], "Monday pace report incomplete")

    def test_contract_calls_notify_and_limits_writes_to_owned_fields(self):
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        self.assertIn("policy.tooling.scripts.forecast_notify --tracking-input", contract)
        self.assertIn("only Opportunity ForecastCategoryName and Contact Email", contract)
        self.assertIn("CloseDate and Next Step fixes are handoffs to Pipeline, never forecast writes", contract)
        report = (WORKFLOW / "references/report-format.md").read_text()
        self.assertIn("Pipeline handoffs have no write-approval letters", report)
        rules = (ROOT / "_core/rules.md").read_text()
        followup = rules.split('<a id="followup_task"></a>', 1)[1].split('<a id=', 1)[0]
        self.assertNotIn("forecast-weekly", followup)

    def test_forecast_sources_allow_slack_while_tracking_keeps_its_scope(self):
        contract = (WORKFLOW / "CONTEXT.md").read_text()
        audit = next(line for line in contract.splitlines() if line.startswith("| Sources,"))
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.assertIn("slack", policy["forecast"]["sources"])
        self.assertIn("including read-only Slack", audit)
        self.assertNotIn("No Slack", audit)
        self.assertIn("No warehouse reads", audit)
        self.assertIn("Tracking reads no Slack", contract)
