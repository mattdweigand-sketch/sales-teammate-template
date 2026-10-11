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

    def test_s1_missing_amount_flags_on_weekly_and_requested_days(self):
        for amount in (None, 0, ""):
            self.record["Amount"] = amount
            result = hygiene_check.check(self.record, self.policy, {}, self.friday)
            self.assertEqual(result["review_scope"], "qualification")
            self.assertEqual(result["blank_fields"], ["Amount"])
            self.assertIn("blank_field", result["triggers"])
        result = hygiene_check.check(self.record, self.policy, {}, self.friday + timedelta(days=1))
        self.assertEqual(result["blank_fields"], ["Amount"])
        self.assertIn("blank_field", result["triggers"])

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
        if identifier not in {row['id'] for row in self.data['deals']}:
            self.data['deals'].append({'id':identifier,'name':'Early customer','flags':['blank_field']})
            self.data['counts']['reviewed']+=1
        self.data.setdefault('triage',[]).append({'deal':identifier,'name':'Early customer','reason':'Triage owns the next step','triage_next_step':True})
        return {"deal": identifier, "name": "Early customer", "stage": "S1", "action": "triage",
                "summary": "Triage owns the next step."}

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

    def test_closed_lost_accepts_operator_stated_no_with_quote_and_date(self):
        row = self.row()
        row.update(action="closed_lost", operator_stated_no={"quote": "No interest in an enterprise contract.", "date": "2026-09-27"},
                   last_buyer_activity="2026-09-27", evidence_complete=True, upcoming_event=True)
        self.data["friday"]["qualification"] = [row]
        self.render.ok("report", self.data)
        for stated in (None, {}, {"quote": " ", "date": "2026-09-27"}, {"quote": "No.", "date": "bad"},
                       {"quote": "No.", "date": "2026-09-29"}, {"quote": "No."}, "No."):
            data = copy.deepcopy(self.data)
            data["friday"]["qualification"][0]["operator_stated_no"] = stated
            self.render.fails("report", data, "Operator's stated no")

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

    def test_unknowns_require_question_and_next_step_requires_triage(self):
        self.data["friday"]["qualification"] = [{**self.row(), "action": "needs_input"}]
        self.render.fails("report", self.data, "existing open question")
        self.data["friday"]["qualification"] = [self.row()]
        self.data["triage"] = []
        self.render.fails("report", self.data, "read-only triage finding")

    def test_weekly_pass_required_on_requested_weekday_too(self):
        del self.data["friday"]["qualification"]
        self.render.fails("report", self.data, "friday.qualification is required")
        data = render_tests.base()
        del data["friday"]["qualification"]
        self.render.fails("report", data, "friday.qualification is required")

    def test_contract_preserves_evidence_and_approval_gates(self):
        workflow = ROOT / "workspaces/pipeline/workflows/pipeline-review"
        text = (workflow / "references/proposals.md").read_text()
        for phrase in ("buyer evidence", "Never propose moving an early stage up", "non-editable formula", "never ARR__c",
                       "fresh reads, approval, and readback", "no upcoming Event", "Operator's stated no"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()


class StageMoveGateTests(unittest.TestCase):
    """Closed Won and early-stage upward moves are rejected in proposal and receipt modes, with or without a qualification row."""

    def setUp(self):
        self.render = render_tests.Render("runTest")
        self.render.setUp()

    def tearDown(self):
        self.render.tearDown()

    def letter(self, current, proposed, mode, status="proposed", qualification=None):
        data = render_tests.friday(render_tests.base())
        letter = data["friday"]["letters"][0]
        letter["status"] = status
        letter["change"].update(field="StageName", current=current, proposed=proposed)
        if qualification is not None:
            data["friday"]["qualification"] = qualification
        if mode == "receipt":
            data["writes"] = []
        return data

    def qualification_row(self, stage):
        return [{"deal": render_tests.BIO, "name": "Acme Devices", "stage": stage, "action": "triage",
                 "summary": "Triage owns the next step."}]

    def run_mode(self, mode, data, needle=None):
        coverage = None if mode == "receipt" else render_tests.READY
        if needle is None:
            return self.render.ok(mode, data, coverage)
        return self.render.fails(mode, data, needle, coverage)

    def test_early_stage_upward_move_without_qualification_row_fails_in_both_modes(self):
        for mode, status in (("report", "proposed"), ("receipt", "approved")):
            for current, proposed in (("S1", "S2"), ("S0", "S1"), ("S0", "S3"), ("S1 - Qualify", "S2")):
                with self.subTest(mode=mode, current=current, proposed=proposed):
                    data = self.letter(current, proposed, mode, status=status)
                    self.assertEqual(data["friday"]["qualification"], [])
                    self.run_mode(mode, data, "never proposes an upward stage move from an early stage")

    def test_early_stage_upward_move_with_qualification_row_still_fails(self):
        for mode, status in (("report", "proposed"), ("receipt", "approved")):
            with self.subTest(mode=mode):
                data = self.letter("S1", "S2", mode, status=status, qualification=self.qualification_row("S1"))
                self.run_mode(mode, data, "never proposes an upward stage move")

    def test_closed_won_is_rejected_in_both_modes(self):
        for mode, status in (("report", "proposed"), ("receipt", "approved")):
            for current in ("S3", "S5", "S1"):
                with self.subTest(mode=mode, current=current):
                    data = self.letter(current, "Closed Won", mode, status=status)
                    self.run_mode(mode, data, "never proposes Closed Won")

    def test_stage_change_without_a_readable_source_stage_fails(self):
        for current in (None, "", "Qualify", 3):
            with self.subTest(current=current):
                data = self.letter(current, "S3", "report")
                self.run_mode("report", data, "needs its current source stage")
        data = self.letter("S2", "S9", "report")
        self.run_mode("report", data, "must be a policy stage or Closed Lost")

    def test_s2_to_s3_and_nonblank_amount_corrections_stay_permitted(self):
        for mode, status in (("report", "proposed"), ("receipt", "approved")):
            with self.subTest(mode=mode, change="S2 to S3"):
                self.run_mode(mode, self.letter("S2", "S3", mode, status=status))
            with self.subTest(mode=mode, change="Amount"):
                data = render_tests.friday(render_tests.base())
                letter = data["friday"]["letters"][0]
                letter["status"] = status
                letter["change"].update(field="Amount", current=90000, proposed=100000)
                if mode == "receipt":
                    data["writes"] = []
                self.run_mode(mode, data)

    def test_early_stage_gate_follows_policy_not_a_hardcoded_list(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.assertEqual(policy["pipeline"]["early_stages"], ["S0", "S1"])
        data = self.letter("S2", "S3", "report")
        self.run_mode("report", data)

    def test_next_steps_write_is_never_an_approved_change(self):
        """G1. The renderer has no implicit Next_Steps__c key, so a receipt can never report one as Written."""
        data = render_tests.base()
        block = data["blocks"][0]
        block["status"] = "approved"
        block["next_step"]["proposed"] = "Next: call Pat · Operator · 10/9/26"
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": render_tests.BIO, "field": "Next_Steps__c",
                           "outcome": "written"}]
        result = self.render.call("receipt", data, None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot propose a next-step change", result.stderr)
        self.assertIn("Next_Steps__c is not an approved change of 1", result.stderr)
