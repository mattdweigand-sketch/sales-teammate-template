"""Approved target-call lookup and full-window Coach stakeholder retrieval."""
from pathlib import Path
import unittest

from test_skill_contracts import loaded_contract_text

ROOT = Path(__file__).resolve().parents[2]
COACH = ROOT / "workspaces/deal-coaching/workflows/deal-coach"


class CoachMomentumCoverageTests(unittest.TestCase):
    def test_rule_line_budget_preserves_anchor_block_separation(self):
        lines = (ROOT / "_core/rules.md").read_text().splitlines()
        note_prefix = lines.index('<a id="note_prefix"></a>**note_prefix**')
        evidence_heading = lines.index("## Evidence and tooling")
        self.assertEqual(lines[note_prefix - 1], "")
        self.assertEqual(lines[evidence_heading + 1], '<a id="handoff_delivery"></a>**handoff_delivery**')
        self.assertLessEqual(len(lines), 200)

    def test_momentum_rule_preserves_bounds_and_uses_exact_approved_stop_scope(self):
        rules = (ROOT / "_core/rules.md").read_text()
        momentum = rules.split('<a id="momentum"></a>', 1)[1].split('<a id="email_body"></a>', 1)[0]
        normalized = " ".join(momentum.split())
        self.assertIn(
            "Windows of at most `window_days`, newest first, one request each. "
            "For a target-call lookup, stop at the first match. "
            "Coach stakeholder coverage reads every Account-filtered window within `lookback_days`. "
            "Never search past `lookback_days`.", normalized)
        self.assertIn("Always pass `salesforceAccountId=<18-char AccountId>`", momentum)
        self.assertIn("The interaction-sync sweep branch", momentum)
        self.assertNotIn("request each. Stop at the first match.", momentum)

    def test_stakeholder_reference_reads_all_account_filtered_windows(self):
        report = (COACH / "references/report-format.md").read_text()
        coverage = report.split("After the per-deal reviews", 1)[1].split("## Pre-meeting", 1)[0]
        self.assertIn("every Account-filtered Momentum window", coverage)
        self.assertIn("policy.momentum.lookback_days", coverage)
        self.assertIn("not a target-call lookup", coverage)
        self.assertIn("rules#momentum", loaded_contract_text(COACH))

    def test_monthly_learning_keeps_full_month_sources_and_bounded_momentum(self):
        learning = (COACH / "references/learning.md").read_text()
        self.assertIn("Salesforce call Tasks and Next_Steps__c for the full previous calendar month", learning)
        self.assertIn("intersection of that month and the supported lookback", learning)
        self.assertIn("Account-filtered windows", learning)
        self.assertIn("Read every Account-filtered window in that overlap", learning)
        self.assertIn("out-of-lookback evidence as not checked", learning)


if __name__ == "__main__":
    unittest.main()
