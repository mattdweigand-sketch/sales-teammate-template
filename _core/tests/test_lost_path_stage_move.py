"""Reviewed lost-path inputs and narrow exception proposals, not live CRM proof."""
import copy
import importlib.util
import unittest
from pathlib import Path

import yaml
import test_pipeline_render as render_tests

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lost_path_renderer", render_tests.SCRIPT)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def reviewed(**changes):
    return {"reason": "buyer_deferral", "from_stage": "S3", "evidence_complete": True,
            "buyer_step_within_three_months": False, "employees": 1000, "description": None, **changes}


class LostPathFactsTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.policy["pipeline"]["worth_growing_min_employees"] = 1000
        self.run = renderer.Run(render_tests.base(), self.policy)

    def test_floor_boundary_and_departed_sponsor(self):
        for reason in ("buyer_deferral", "departed_sponsor"):
            for employees, destination in ((0, "Closed Lost"), (999, "Closed Lost"), (1000, "S1"), (1001, "S1")):
                with self.subTest(reason=reason, employees=employees):
                    self.assertEqual(self.run.lost_path_destination(reviewed(reason=reason, employees=employees)), destination)

    def test_floor_is_policy_not_hardcoded(self):
        self.policy["pipeline"]["worth_growing_min_employees"] = 500
        self.assertEqual(self.run.lost_path_destination(reviewed(employees=500)), "S1")
        self.assertEqual(self.run.lost_path_destination(reviewed(employees=499)), "Closed Lost")

    def test_unknown_or_unsupported_facts_never_supply_destination(self):
        invalid = [{"reason": "outbound_followup"}, {"reason": None}, {"from_stage": "S1"}, {"from_stage": "S0"},
                   {"evidence_complete": False}, {"evidence_complete": "true"}, {"buyer_step_within_three_months": True},
                   {"buyer_step_within_three_months": None}, {"employees": None}, {"employees": ""},
                   {"employees": "999"}, {"employees": -1}, {"employees": True}, {"description": {}}]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertIsNone(self.run.lost_path_destination(reviewed(**changes)))
        for key in reviewed():
            facts = reviewed()
            del facts[key]
            self.assertIsNone(self.run.lost_path_destination(facts))
        self.assertIsNone(self.run.lost_path_destination(None))

    def test_blank_native_count_can_use_matt_answer_without_claiming_native_count(self):
        facts = reviewed(employees=None, operator_employee_count={"value": 999, "quote": "The employee count is 999.", "date": "2026-09-27"})
        self.assertEqual(self.run.lost_path_destination(facts), "Closed Lost")
        self.assertIsNone(facts["employees"])
        for changes in ({"date": "2026-09-29"}, {"quote": ""}, {"value": "999"}, {"value": True}):
            bad = copy.deepcopy(facts)
            bad["operator_employee_count"].update(changes)
            self.assertIsNone(self.run.lost_path_destination(bad))

    def test_exception_marker_plain_or_note_prefixed_keeps_small_account_open(self):
        marker = "Size floor exception, kept open by Operator 9/27/26"
        for description in (marker, "9/28/26 SR - " + marker + "\n9/1/26 SR - Existing history."):
            self.assertEqual(self.run.lost_path_destination(reviewed(employees=10, description=description)), "S1")

    def test_marker_date_and_shape_unknown_hold_not_silent_loss(self):
        for marker in ("Size floor exception, kept open by Operator tomorrow", "Size floor exception, kept open by Operator 9/29/26",
                       "Size floor exception, kept open by Operator 2/30/26", "9/29/26 SR - Size floor exception, kept open by Operator 9/27/26"):
            self.assertIsNone(self.run.lost_path_destination(reviewed(employees=10, description=marker)))
        self.assertEqual(self.run.lost_path_destination(reviewed(employees=10, description="9/1/26 SR - Ordinary history.")), "Closed Lost")


class LostPathReportTests(unittest.TestCase):
    def setUp(self):
        self.render = render_tests.Render("runTest")
        self.render.setUp()
        self.render.policy["pipeline"]["worth_growing_min_employees"] = 1000
        self.render.pol.write_text(yaml.safe_dump(self.render.policy))
        self.data = render_tests.friday(render_tests.base())
        self.letter = self.data["friday"]["letters"][0]
        self.letter["change"].update(field="StageName", current="S3", proposed="S1")
        self.letter["lost_path_size"] = reviewed()

    def tearDown(self):
        self.render.tearDown()

    def test_s3_can_move_directly_to_s1_at_floor(self):
        output = self.render.ok("report", self.data)
        self.assertIn("S3", output)
        self.assertIn("S1", output)

    def test_small_s3_goes_closed_lost_not_s1(self):
        self.letter["lost_path_size"]["employees"] = 999
        self.render.fails("report", self.data, "supported size-floor destination")
        self.letter["change"]["proposed"] = "Closed Lost"
        self.render.ok("report", self.data)

    def test_blank_count_and_missing_retrieval_block_stage_letter(self):
        for changes in ({"employees": None}, {"evidence_complete": False}, {"buyer_step_within_three_months": None}):
            self.letter["lost_path_size"] = reviewed(**changes)
            self.render.fails("report", self.data, "supported size-floor destination")
        self.letter["lost_path_size"] = None
        self.render.fails("report", self.data, "supported size-floor destination")

    def test_size_basis_origin_matches_current_s2_plus_stage(self):
        self.letter["lost_path_size"]["from_stage"] = "S2"
        self.render.fails("report", self.data, "origin must match the current S2+ stage")

    def test_existing_criterion_move_without_lost_path_basis_remains_supported(self):
        del self.letter["lost_path_size"]
        self.render.ok("report", self.data)

    def qualification(self, **facts):
        self.letter["change"].update(current="S1", proposed="Closed Lost")
        self.letter["lost_path_size"] = reviewed(employees=999, **facts)
        self.data["friday"]["qualification"] = [{"deal": render_tests.BIO, "name": "Synthetic account", "stage": "S1",
            "action": "closed_lost", "summary": "Previously moved back for a reviewed lost path, below the size floor.",
            "lost_path_size": copy.deepcopy(self.letter["lost_path_size"])}]

    def test_existing_s1_lost_path_review_can_close_without_silence_basis(self):
        self.qualification()
        self.render.ok("report", self.data)

    def test_new_s1_without_prior_backward_move_is_not_size_floor_loss(self):
        self.qualification(from_stage="S1")
        self.render.fails("report", self.data, "reviewed lost-path size below the floor")

    def test_qualification_and_letter_must_use_same_facts(self):
        self.qualification()
        self.letter["lost_path_size"]["employees"] = 1000
        self.render.fails("report", self.data, "same reviewed facts")

    def test_exception_prevents_size_floor_closed_lost(self):
        self.qualification(description="Size floor exception, kept open by Operator 9/27/26")
        self.render.fails("report", self.data, "below the floor without an exception")
        self.data["friday"]["qualification"] = []
        self.letter["change"].update(current="S3", proposed="S1")
        self.render.ok("report", self.data)

    def test_exception_does_not_defeat_independent_matt_no_basis(self):
        self.qualification(description="Size floor exception, kept open by Operator 9/27/26")
        del self.letter["lost_path_size"]
        row = self.data["friday"]["qualification"][0]
        del row["lost_path_size"]
        row["operator_stated_no"] = {"quote": "Close this deal as lost.", "date": "2026-09-27"}
        self.render.ok("report", self.data)

    def test_existing_s1_exception_needs_no_redundant_s1_proposal(self):
        self.letter["change"].update(current="S1", proposed="S1")
        self.render.fails("report", self.data, "without a redundant stage proposal")

    def exception_letter(self):
        self.letter.pop("lost_path_size")
        self.letter["change"].update(field="Description", current="9/1/26 SR - Existing history.", mode="prepend",
                                   proposed="9/28/26 SR - Size floor exception, kept open by Operator 9/27/26")
        self.letter["operator_size_exception"] = {"quote": "Keep this deal open below the size floor.", "date": "2026-09-27"}

    def test_exception_letter_prepend_preserves_exact_baseline(self):
        self.exception_letter()
        baseline = self.letter["change"]["current"]
        self.render.ok("report", self.data)
        self.assertEqual(self.letter["change"]["current"], baseline)

    def test_exception_cannot_overwrite_or_write_other_description(self):
        self.exception_letter()
        self.letter["change"]["mode"] = "replace"
        self.render.fails("report", self.data, "exact dated marker prepended")
        self.letter["change"].update(mode="prepend", proposed="9/28/26 SR - Arbitrary note.")
        self.render.fails("report", self.data, "exact dated marker prepended")

    def test_exception_requires_instruction_and_exact_native_baseline(self):
        self.exception_letter()
        del self.letter["operator_size_exception"]
        self.render.fails("report", self.data, "Operator's reviewed quote and dated instruction")
        self.letter["operator_size_exception"] = {"quote": "Keep open.", "date": "2026-09-29"}
        self.render.fails("report", self.data, "Operator's reviewed quote and dated instruction")
        self.letter["operator_size_exception"]["date"] = "2026-09-27"
        del self.letter["change"]["current"]
        self.render.fails("report", self.data, "exact native Description baseline")

    def test_ambiguous_existing_marker_cannot_be_overridden(self):
        self.exception_letter()
        self.letter["change"]["current"] = "Size floor exception, kept open by Operator unknown"
        self.render.fails("report", self.data, "unambiguous native Description baseline")

    def test_exception_instruction_is_not_write_approval(self):
        self.exception_letter()
        self.data["writes"] = [{"label": "A", "object": "Opportunity", "id": render_tests.BIO,
                               "field": "Description", "outcome": "written"}]
        self.render.fails("receipt", self.data, "only approved labels are written")

    def test_existing_exception_is_not_duplicated(self):
        self.exception_letter()
        self.letter["change"]["current"] = "Size floor exception, kept open by Operator 9/27/26"
        self.render.fails("report", self.data, "already exists, do not duplicate")


class LostPathContractTests(unittest.TestCase):
    def test_shared_stage_trigger_and_cap(self):
        text = (ROOT / "_core/rules.md").read_text()
        self.assertLessEqual(len(text.splitlines()), 200)
        section = text.split('<a id="stage_move">', 1)[1].split('<a id="close_date_basis">', 1)[0]
        for phrase in ("current criterion fails or on a lost path", "at S2 or higher, a buyer deferral or departed sponsor",
                       "buyer-agreed step dated within 3 months", "buyer-named week or month counts",
                       "Operator's follow-up does not", "A lost path may go straight to S1", "Missing retrieval is unknown, not evidence"):
            self.assertIn(phrase, section)
        self.assertTrue(all(len(line) <= 200 for line in section.splitlines()))

    def test_native_reads_and_prior_history_are_bounded_to_owned_deals(self):
        shared = (ROOT / "workspaces/pipeline/references/deal-activity-reads.md").read_text()
        self.assertIn("Account.NumberOfEmployees, Description", shared)
        collect = (ROOT / "workspaces/pipeline/workflows/pipeline-review/references/collect.md").read_text()
        self.assertIn("WHERE OpportunityId IN (<owned S1 ids>) AND Field = 'StageName' ORDER BY CreatedDate", collect)
        self.assertIn("History alone does not establish its lost-path reason", collect)

    def test_blank_count_exception_and_approval_gates_remain_in_owner(self):
        proposals = (ROOT / "workspaces/pipeline/workflows/pipeline-review/references/proposals.md").read_text()
        for phrase in ("Never treat blank as zero", "Newly qualifying S1 deals that never moved back are unaffected",
                       "lettered Opportunity Description proposal", "Preserve all existing text under `rules#note_prefix`",
                       "letter approval, fresh-read and readback gates", "does not defeat an independent buyer no"):
            self.assertIn(phrase, proposals)
        interaction = (ROOT / "workspaces/pipeline/workflows/interaction-sync/references/proposals.md").read_text()
        self.assertIn("`StageName` per `rules#stage_move` with supporting transcript evidence", interaction)
        self.assertIn("Closed Lost stays with pipeline-review", interaction)


if __name__ == "__main__":
    unittest.main()
