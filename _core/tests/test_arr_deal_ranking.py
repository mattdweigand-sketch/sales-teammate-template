import unittest
from pathlib import Path

import yaml
import test_pipeline_render as render_tests

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline/workflows/pipeline-review"
COACH = ROOT / "workspaces/deal-coaching/workflows/deal-coach"
FORECAST = ROOT / "workspaces/forecasting/workflows/forecast-weekly"


class RankingContractTests(unittest.TestCase):
    def test_coach_uses_policy_size_and_no_amount_fallback(self):
        text = (COACH / "references/report-format.md").read_text()
        self.assertIn("Rank by `policy.forecast.amount_field` descending with blanks last", text)
        self.assertIn("An Amount without ARR ranks as blank", text)
        self.assertIn("Never fall back to Amount", text)
        self.assertNotIn("Rank by Amount", text)

    def test_forecast_scope_and_upside_use_policy_size(self):
        buckets = (FORECAST / "references/buckets.md").read_text()
        self.assertIn("Upside: S2 or S3 with `policy.forecast.amount_field` set", buckets)
        self.assertIn("next-quarter S2+ deals with `policy.forecast.amount_field` set", buckets)
        self.assertIn("An Amount without ARR ranks as blank", buckets)
        for name in ("buckets", "collect", "report-format"):
            text = (FORECAST / f"references/{name}.md").read_text()
            self.assertIn("policy.forecast.amount_field", text)
            self.assertIn("Never fall back to Amount", text)
            self.assertNotIn("with an Amount", text)
            self.assertNotIn("with Amount", text)
        self.assertNotIn("without Amount", (FORECAST / "references/report-format.md").read_text())

    def test_pipeline_queries_size_and_documents_ranking(self):
        self.assertIn("<policy.forecast.amount_field>", (PIPELINE / "references/collect.md").read_text())
        text = (PIPELINE / "references/report-format.md").read_text()
        self.assertIn("earlier dates, `policy.forecast.amount_field` descending with blanks last", text)
        self.assertIn("Never fall back to Amount when ARR is blank", text)

    def test_new_policy_reads_are_branch_bounded(self):
        self.assertIn("Deal-review only: `forecast.amount_field`", (COACH / "CONTEXT.md").read_text())
        self.assertIn("Weekday Top 3 only: `forecast.amount_field`", (PIPELINE / "CONTEXT.md").read_text())


class TopActionRankingTests(unittest.TestCase):
    def setUp(self):
        self.renderer = render_tests.Render("runTest")
        self.renderer.setUp()
        self.addCleanup(self.renderer.tearDown)

    def candidates(self):
        return [self.renderer.today_candidate(),
                self.renderer.today_candidate(render_tests.ROUX, "Beacon Labs"),
                self.renderer.today_candidate(render_tests.ROYAL, "Corvid Foods")]

    def section(self, data, *extra):
        output = self.renderer.ok("report", data, render_tests.READY, *extra)
        return output.split("## Top 3 actions today", 1)[1].split("## Clear recommendations", 1)[0]

    def test_arr_descending_missing_arr_never_uses_amount(self):
        data = render_tests.base()
        data["today_actions"] = self.candidates()
        for candidate, size in zip(data["today_actions"], (None, "100.01", "100.02")):
            candidate.update(ARR__c=size, Amount=999999999 if size is None else 1)
        section = self.section(data)
        self.assertIn("Priority 1 · [Corvid Foods]", section)
        self.assertIn("Priority 2 · [Beacon Labs]", section)
        self.assertIn("Priority 3 · [Acme Devices]", section)
        data["today_actions"].reverse()
        self.assertEqual(section, self.section(data))

    def test_zero_is_set_and_blanks_last(self):
        for blank in (None, "", "absent"):
            data = render_tests.base()
            data["today_actions"] = self.candidates()[:2]
            if blank != "absent":
                data["today_actions"][0]["ARR__c"] = blank
            data["today_actions"][1]["ARR__c"] = 0
            with self.subTest(blank=blank):
                self.assertIn("Priority 1 · [Beacon Labs]", self.section(data))

    def test_configured_field_not_literal_arr_or_amount(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        policy["forecast"]["amount_field"] = "Configured_ARR__c"
        path = self.renderer.dir / "policy.yaml"
        path.write_text(yaml.safe_dump(policy))
        data = render_tests.base()
        data["today_actions"] = self.candidates()[:2]
        data["today_actions"][0].update(ARR__c=999999, Amount=999999, Configured_ARR__c=1)
        data["today_actions"][1].update(ARR__c=None, Amount=None, Configured_ARR__c=2)
        self.assertIn("Priority 1 · [Beacon Labs]", self.section(data, "--policy", str(path)))

    def test_kind_and_date_precede_size(self):
        data = render_tests.base()
        data["today_actions"] = [self.renderer.buyer_candidate(),
                                 self.renderer.today_candidate(render_tests.ROUX, "Beacon Labs", when="2026-09-27", ARR__c=1),
                                 self.renderer.today_candidate(render_tests.ROYAL, "Corvid Foods", ARR__c=999999999)]
        section = self.section(data)
        self.assertIn("Priority 1 · [Acme Devices]", section)
        self.assertIn("Priority 2 · [Beacon Labs]", section)

    def test_invalid_size_rejected_before_render(self):
        for value in (True, False, "unknown", "NaN", "Infinity", -1, [], {}):
            data = render_tests.base()
            data["today_actions"] = [self.renderer.today_candidate(ARR__c=value)]
            with self.subTest(value=value):
                self.renderer.fails("report", data, "size must be")
