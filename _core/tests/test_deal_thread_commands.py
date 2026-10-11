"""Typed deal commands reuse guarded one-deal writes, never triage receipts."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline"
TRIAGE = PIPELINE / "workflows/task-triage-speed-run"

APPROVED_RULE_LINES = (  # approved wording, in document order
    "- Exceptions are interaction-sync call logging, signal-followup's proven-send Task, Close's downstream-status Task, customer-review's check-in creates and Operator's typed deal-thread commands.",
    "  In one-deal mode or a deal thread, Operator's typed command is the quoted source for that deal's Task or next-step change. Scheduled runs keep the evidence rules above.",
    "  After approved writes, send each affected deal thread a receipt of at most 3 lines. Deal threads never act on triage items unprompted or ask Operator about them. Receipts are context only.",
    "  Deal threads keep stage, close date, Amount, research and inbound buyer replies. On Operator's typed command they propose any change for that deal, including Tasks and next steps.",
    "- Only triage, interaction-sync, Close and a deal thread on Operator's typed command write `Next_Steps__c`. Close writes only its onboarding entry. Triage proposes each pair once, under one approval.",
    "- Never complete a deal's current-action Task without naming its replacement in the same proposal, new or verified existing. Extra open Tasks and date mismatches stay with triage unprompted.",
)


class DealThreadCommandContracts(unittest.TestCase):
    def test_six_approved_rule_lines_and_two_hundred_line_budget(self):
        lines = (ROOT / "_core/rules.md").read_text().splitlines()
        self.assertLessEqual(len(lines), 200)
        positions = []
        for expected in APPROVED_RULE_LINES:
            with self.subTest(line=expected[:60]):
                self.assertEqual(lines.count(expected), 1)
                positions.append(lines.index(expected))
        self.assertEqual(positions, sorted(positions))

    def test_typed_command_is_not_approval_and_receipts_cannot_trigger_work(self):
        agents = (PIPELINE / "AGENTS.md").read_text()
        for expected in (
            "Operator's typed command may request any change for that deal",
            "Show the exact labeled proposal",
            "No typed command is itself write approval",
            "only after Operator's label approval",
            "rules#approval", "rules#write_protocol", "rules#repo_currency",
            "Triage alone owns unprompted Task and next-step proposals",
            "Receipts are context only",
            "Never act unprompted on triage items or ask Operator about them",
            "No receipt to triage is needed because triage fresh-reads before its own writes",
            "The shared rule includes Operator's typed deal-thread commands",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, agents)
        self.assertNotIn("all four exceptions", agents)
        self.assertNotIn("not a deal-thread field proposal", agents)

    def test_deal_entry_snapshots_consumed_mechanics_without_inventing_workflow(self):
        agents = (PIPELINE / "AGENTS.md").read_text()
        for expected in (
            "deal_thread_entry", "actually consumed sources",
            "Do not claim or load a workflow the deal thread never ran",
            'references/next-steps.md` "One deal"',
            'references/writes.md` "Writes"',
            "not its full queue, section walk, closeout or receipt delivery",
        ):
            self.assertIn(expected, agents)
        interfaces = (ROOT / "_core/scripts/interfaces.md").read_text()
        self.assertIn("Manual triage keeps writer=triage and adds manual_one_deal", interfaces)
        self.assertIn("Deal threads instead use `deal_thread_entry`", interfaces)
        self.assertIn("Use writer=triage with manual_one_deal for these mechanics", agents)
        self.assertIn("Keep `deal_thread_entry`", agents)

    def test_pair_date_duplicate_and_replacement_gates_are_reused(self):
        agents = (PIPELINE / "AGENTS.md").read_text()
        for expected in (
            "exact next-step and current-action Task pair in one proposal",
            "rules#next_steps_format", "rules#note_prefix", "policy.salesforce.note_prefix",
            "task_reschedule_check", "proposal and prewrite",
            "Recheck duplicates immediately before writing",
            "Never complete a current-action Task without its named replacement",
            "read every changed record back",
        ):
            self.assertIn(expected, agents)
        one_deal = (TRIAGE / "references/next-steps.md").read_text().split("## One deal\n", 1)[1]
        for expected in (
            "typed in any project thread", "all related open Tasks",
            "Keep writer=triage and use manual_one_deal",
            "No typed command is itself write approval",
        ):
            self.assertIn(expected, one_deal)

    def test_workflow_bans_remain_unprompted_not_a_typed_command_veto(self):
        close = (PIPELINE / "workflows/close/references/proposals.md").read_text()
        self.assertIn("Deal-thread runs make no unprompted Task proposals", close)
        self.assertIn("Operator's typed Task commands use Pipeline AGENTS.md", close)
        self.assertNotIn("never duplicated or proposed by deal threads", close)
        triage = (TRIAGE / "CONTEXT.md").read_text()
        self.assertIn("never delegate unprompted Task proposals", triage)
        self.assertNotIn("never Task proposals there", triage)
        # Pipeline-review's findings still belong to triage, not deal threads.
        review = (PIPELINE / "workflows/pipeline-review/references/proposals.md").read_text()
        self.assertIn("No Task or next-step change, approval label or delivery command belongs to those rows", review)
        self.assertIn("They never route to deal threads", review)


if __name__ == "__main__":
    unittest.main()
