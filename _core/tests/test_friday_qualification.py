import copy
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import yaml
import test_pipeline_render as render_tests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_core/scripts"))
import hygiene_check


class QualificationTriggerTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.friday = datetime.fromisoformat("2026-10-02T09:00:00-07:00")
        self.record = {"Id": "006qualification", "StageName": "S1", "AccountId": "account",
                       "Amount": None, "Next_Steps__c": "10/2/26 SR - Confirm the plan by 10/6/26.",
                       "CloseDate": "2026-12-01"}

    def test_s1_missing_amount_flags_on_friday_only(self):
        for amount in (None, 0, ""):
            self.record["Amount"] = amount
            result = hygiene_check.check(self.record, self.policy, {}, self.friday)
            self.assertEqual(result["review_scope"], "qualification")
            self.assertEqual(result["blank_fields"], ["Amount"])
            self.assertIn("blank_field", result["triggers"])
        result = hygiene_check.check(self.record, self.policy, {}, self.friday + timedelta(days=1))
        self.assertNotIn("blank_fields", result)
        self.assertEqual(result["triggers"], [])

    def test_s0_does_not_inherit_s1_or_s2_amount_requirements(self):
        self.record["StageName"] = "S0"
        result = hygiene_check.check(self.record, self.policy, {}, self.friday)
        self.assertEqual(result["blank_fields"], [])
        self.record.update(StageName="S1", Amount=100000)
        self.assertEqual(hygiene_check.check(self.record, self.policy, {}, self.friday)["blank_fields"], [])

    def test_silence_boundary_uses_policy_and_requires_reviewed_evidence(self):
        cutoff = self.policy["pipeline"]["closed_lost_silence_days"]
        for days, expected in ((cutoff - 1, False), (cutoff, True), (cutoff + 1, True)):
            last = (self.friday.date() - timedelta(days=days)).isoformat()
            self.assertEqual(hygiene_check.closed_lost_silence_eligible(last, self.friday, self.policy, True, False), expected)
        last = (self.friday.date() - timedelta(days=cutoff)).isoformat()
        for complete, upcoming in ((False, False), ("true", False), (True, True), (True, None)):
            self.assertFalse(hygiene_check.closed_lost_silence_eligible(last, self.friday, self.policy, complete, upcoming))

    def test_missing_invalid_or_future_activity_is_not_silence(self):
        for last in (None, "", "unknown", "2026-10-03"):
            self.assertFalse(hygiene_check.closed_lost_silence_eligible(last, self.friday, self.policy, True, False))

    def test_exact_approved_policy_text_and_amount_not_formula(self):
        text = (ROOT / "_core/policy.yaml").read_text()
        self.assertIn('''  stages: [S2, S3, S4, S5]         # hygiene scope. S0 and S1 get the Friday qualification pass only
  early_stages: [S0, S1]           # Friday qualification pass, Closed Lost per closed_lost_silence_days
  early_required_fields:
    S1: [Amount]                   # quota ARR needs a deal size by S1
''', text)
        self.assertEqual(self.policy["pipeline"]["early_required_fields"], {"S1": ["Amount"]})


class QualificationReportTests(unittest.TestCase):
    def setUp(self):
        self.render = render_tests.Render("runTest")
        self.render.setUp()
        self.data = render_tests.friday(render_tests.base())

    def tearDown(self):
        self.render.tearDown()

    def row(self, identifier=render_tests.BIO):
        return {"deal": identifier, "name": "Early customer", "stage": "S1", "action": "next_step",
                "next_step_date": "2026-10-05", "summary": "Confirm a dated qualification step."}

    def test_full_count_but_ten_rows_at_most(self):
        self.data["friday"]["qualification"] = [self.row(f"006000000000{number:06d}") for number in range(12)]
        self.data["friday"]["qualification"][0]["summary"] += "\nSecond line."
        out = self.render.ok("report", self.data)
        section = out.split("## Qualification", 1)[1].split("## Record proposals", 1)[0]
        self.assertIn("12 early-stage deals reviewed. Showing 10.", section)
        self.assertEqual(section.count("- [Early customer]"), 10)
        self.assertNotIn("\nSecond line.", section)

    def test_closed_lost_requires_silence_and_no_upcoming_event(self):
        row = self.row()
        row.update(action="closed_lost", last_buyer_activity="2026-08-29", evidence_complete=True, upcoming_event=False)
        self.data["friday"]["qualification"] = [row]
        self.render.ok("report", self.data)
        for change in ({"last_buyer_activity": "2026-08-30"}, {"upcoming_event": True}, {"evidence_complete": False}):
            data = copy.deepcopy(self.data)
            data["friday"]["qualification"][0].update(change)
            self.render.fails("report", data, "reviewed silence")

    def test_upward_stage_move_is_rejected_even_with_evidence(self):
        self.data["friday"]["qualification"] = [self.row()]
        self.data["friday"]["letters"][0]["change"].update(field="StageName", current="S1", proposed="S2")
        self.render.fails("report", self.data, "never proposes an upward stage move")

    def test_s1_amount_requires_reviewed_buyer_evidence_and_missing_amount(self):
        self.data["friday"]["qualification"] = [{**self.row(), "missing_amount": True}]
        letter = self.data["friday"]["letters"][0]
        letter["change"].update(field="Amount", current=None, proposed=100000)
        self.render.fails("report", self.data, "reviewed buyer evidence")
        letter["buyer_confirmed"] = True
        letter["evidence"] = [{"source": "Salesforce", "date": "9/28/26", "fact": "Buyer confirmed an annual amount of $100,000 in the quote."}]
        self.render.ok("report", self.data)
        letter["change"]["current"] = 100000
        self.render.fails("report", self.data, "missing S1 Amount")
        letter["change"]["current"] = None
        self.data["friday"]["qualification"][0]["stage"] = "S0"
        self.render.fails("report", self.data, "missing S1 Amount")

    def test_unknowns_require_question_and_next_step_requires_date(self):
        self.data["friday"]["qualification"] = [{**self.row(), "action": "needs_input"}]
        self.render.fails("report", self.data, "existing open question")
        self.data["friday"]["qualification"] = [{**self.row(), "next_step_date": None}]
        self.render.fails("report", self.data, "next_step_date")

    def test_friday_requires_pass_and_weekdays_exclude_it(self):
        del self.data["friday"]["qualification"]
        self.render.fails("report", self.data, "friday.qualification is required")
        data = render_tests.base()
        data["friday"] = {"qualification": [self.row()]}
        self.render.fails("report", data, "qualification is Friday only")

    def test_contract_preserves_evidence_and_approval_gates(self):
        workflow = ROOT / "workspaces/pipeline/workflows/pipeline-review"
        text = (workflow / "references/proposals.md").read_text()
        for phrase in ("buyer evidence", "Never propose moving an early stage up", "non-editable formula", "never ARR__c",
                       "fresh reads, approval, and readback", "no upcoming Event"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
