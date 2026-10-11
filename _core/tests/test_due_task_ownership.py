"""Contract boundaries for one due-Task owner and one Next Steps handoff."""
import unittest
from pathlib import Path

from test_skill_contracts import loaded_contract_text

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline/workflows"


class DueTaskOwnershipContracts(unittest.TestCase):
    def test_closed_won_downstream_tasks_name_a_standalone_close_receiver(self):
        route = (ROOT / "workspaces/pipeline/CONTEXT.md").read_text()
        contract = (PIPELINE / "close/CONTEXT.md").read_text()
        for name, text in (("Pipeline routing", route), ("Close contract", contract)):
            with self.subTest(name=name):
                self.assertIn("standalone Pipeline run", text)
                self.assertIn("`/close <OpportunityId>`", text)
                self.assertIn("downstream verification and initial proposal E", text)
                self.assertIn("evidence only", text)
        proposals = (PIPELINE / "close/references/proposals.md").read_text()
        self.assertIn("Deal-thread runs make no unprompted Task proposals", proposals)
        self.assertIn("Operator's typed Task commands use Pipeline AGENTS.md", proposals)
        self.assertIn("Never complete, reschedule or replace any Operator-owned open Task", proposals)
        self.assertIn("`approved <label>`", proposals)

    def test_exact_matt_owned_queue_and_unknown_owner_hold_are_canonical(self):
        rules = (ROOT / "_core/rules.md").read_text()
        for expected in ("Triage alone manages Operator-owned open sales Tasks",
                         "OwnerId equal to the run user", "Other writers neither create nor change them",
                         "Other owners' Tasks keep their current workflow behavior",
                         "Missing or unreadable owner evidence holds that Task as needs-input",
                         "Recheck ownership immediately before each write"):
            self.assertIn(expected, rules)
        agents = (ROOT / "workspaces/pipeline/AGENTS.md").read_text()
        self.assertIn("write boundaries are defined only in `rules#task_date_coordination`", agents)
        self.assertIn("receipts give verified written context", agents)
        self.assertIn("Other owners' Tasks keep current behavior", agents)

    def test_every_existing_task_writer_loads_the_guard_and_preserves_other_owners(self):
        for workflow in ("close",):
            with self.subTest(workflow=workflow):
                loaded = loaded_contract_text(PIPELINE / workflow)
                self.assertIn("rules#task_date_coordination", loaded)
                for expected in ("Triage owns Task <Id>", "Other owners keep current behavior",
                                 "needs-input", "before writing", "duplicate"):
                    self.assertIn(expected, loaded)

    def test_collect_reads_native_owner_state_not_just_task_dates(self):
        for workflow, reference in (("pipeline-review", "collect"), ("interaction-sync", "reconcile"),
                                    ("close", "proposals"), ("task-triage-speed-run", "collect")):
            with self.subTest(workflow=workflow):
                text = (PIPELINE / workflow / "references" / f"{reference}.md").read_text()
                if workflow in ("pipeline-review", "task-triage-speed-run"):
                    self.assertIn("deal-activity-reads.md", text)
                    text += (ROOT / "workspaces/pipeline/references/deal-activity-reads.md").read_text()
                self.assertIn("OwnerId", text)
                self.assertIn("IsClosed", text)
                self.assertIn("ActivityDate", text)

    def test_existing_next_action_completes_due_task_without_duplicate_or_stuck_completion(self):
        writes = (PIPELINE / "task-triage-speed-run/references/writes.md").read_text()
        for expected in ("When an open Task already holds the next action", "name it as `reuse existing`",
                         "After approval, verify it still holds that action, write and read back any displayed next step",
                         "Create nothing", "Create and read back the matching Task only when none already holds the next action",
                         "Re-propose completion with that Id for fresh approval",
                         "It is not a permanent completion blocker", "Recheck duplicates before any create"):
            self.assertIn(expected, writes)
        walk = (PIPELINE / "task-triage-speed-run/references/walk.md").read_text()
        self.assertIn("verified existing replacement", walk)
        self.assertEqual(walk.count("?"), 1)

    def test_receipt_reports_written_pair_without_another_proposal(self):
        writes = (PIPELINE / "task-triage-speed-run/references/writes.md").read_text()
        for expected in ("at most 3 lines", "verified written next step and Task links", "never a request for another field or Task proposal"):
            self.assertIn(expected, writes)
        proposals = (PIPELINE / "pipeline-review/references/proposals.md").read_text()
        self.assertIn('Triage owns the next step', proposals)
        self.assertIn('No Task or next-step change', proposals)

    def test_call_logging_retains_full_post_call_task_behavior_in_deal_threads(self):
        proposals = (PIPELINE / "interaction-sync/references/proposals.md").read_text()
        self.assertIn("**A. Completed-call Task.** Status Completed", proposals)
        self.assertIn("including in deal threads", proposals)
        self.assertIn("**F. Complete open Tasks.**", proposals)
        self.assertIn("F applies only after that call Task is verified", proposals)
        self.assertIn("One `approved B` covers both sides", proposals)
        self.assertIn("reschedule by exact ID before creating another", proposals)
        loaded = loaded_contract_text(PIPELINE / "interaction-sync")
        self.assertIn("rules#task_date_coordination", loaded)
        self.assertIn("Missing or unreadable OwnerId holds that Task as needs-input", loaded)
        writes = (PIPELINE / "task-triage-speed-run/references/writes.md").read_text()
        self.assertIn("Skip Tasks interaction-sync already handled, verified against fresh native state and its receipt", writes)

    def test_ten_five_safeguards_and_nonatomic_limit_remain(self):
        for workflow in ("pipeline-review", "interaction-sync"):
            proposals = (PIPELINE / workflow / "references/proposals.md").read_text()
            self.assertIn("rules#write_protocol", proposals)
            self.assertIn("Rerun" if workflow == "interaction-sync" else "shared native Activity reads", proposals)
        rules = (ROOT / "_core/rules.md").read_text()
        for expected in ("changed baseline stops the old proposal", "never reuse the old approval",
                         "Fresh reads are not an atomic lock", "Never create a duplicate"):
            self.assertIn(expected, rules)

    def test_named_exceptions_preserve_initial_create_contracts_and_add_typed_commands(self):
        rules = (ROOT / "_core/rules.md").read_text()
        for expected in ("interaction-sync call logging", "signal-followup's proven-send Task",
                         "Close's downstream-status Task", "customer-review's check-in creates",
                         "Operator's typed deal-thread commands", "Other initial Tasks enter triage when due"):
            self.assertIn(expected, rules)
        agents = (ROOT / "workspaces/pipeline/AGENTS.md").read_text()
        self.assertIn("Deal-thread, pipeline-review and triage write boundaries are defined only", agents)

    def test_future_tasks_have_one_canonical_duplicate_only_exception(self):
        rules = (ROOT / "_core/rules.md").read_text()
        lines = [line for line in rules.splitlines() if line.startswith("- Future-dated Tasks")]
        self.assertEqual(len(lines), 1)
        self.assertIn("never enter scheduled triage or influence its decisions, except the pre-create duplicate check", lines[0])
        self.assertIn("exact next action", lines[0])
        for reference in ("collect", "walk", "daily"):
            text = (PIPELINE / "task-triage-speed-run/references" / f"{reference}.md").read_text()
            self.assertIn("rules#task_date_coordination" if reference == "walk" else "pre-create duplicate check", text)
        collect = (PIPELINE / "task-triage-speed-run/references/collect.md").read_text()
        self.assertIn("Review current-action equivalence without future Tasks", collect)
        self.assertNotIn("including future Tasks. An existing", collect)

    def test_task_gap_approval_is_main_pass_pair_from_native_next_step(self):
        contract = (PIPELINE / "task-triage-speed-run/CONTEXT.md").read_text()
        collect = (PIPELINE / "task-triage-speed-run/references/collect.md").read_text()
        shared = (ROOT / "workspaces/pipeline/references/deal-activity-reads.md").read_text()
        writes = (PIPELINE / "task-triage-speed-run/references/writes.md").read_text()
        self.assertIn('"Task gaps"', contract)
        for expected in ("owned open Opportunities", "Next_Steps__c", "fully paged"):
            self.assertIn(expected, shared)
        self.assertIn('hasMore false', collect)
        for expected in ("**Task gap.**", "never complete another Task under a gap approval", "Operator-owned Not Started Task", "verify every field by native readback"):
            self.assertIn(expected, writes)

    def test_deal_followup_drafts_use_same_approval_evidence_and_readback_path(self):
        drafts = (PIPELINE / "task-triage-speed-run/references/drafts.md").read_text()
        writes = (PIPELINE / "task-triage-speed-run/references/writes.md").read_text()
        self.assertIn("Deal Task follow-up drafts use this same path", drafts)
        self.assertIn("Never delegate its proposal. Never send.", drafts)
        self.assertIn("Includes deal Task follow-ups", writes)
        self.assertIn("A failed or unverified draft gets no next-step, completion or next-Task write", writes)
        self.assertIn("Existing drafts or notes that say a draft exists do not qualify", writes)
