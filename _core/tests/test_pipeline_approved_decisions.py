"""Pin Operator's approved Pipeline audit decisions without expanding write authority."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "workspaces/pipeline/workflows"


class ApprovedPipelineDecisions(unittest.TestCase):
    def test_history_comment_matches_exact_approval(self):
        policy = (ROOT / "_core/policy.yaml").read_text()
        self.assertIn(
            "  history_days: 90                     # Salesforce activity lookback. Momentum uses momentum.lookback_days\n",
            policy,
        )

    def test_send_hold_comments_match_exact_approval(self):
        policy = (ROOT / "_core/policy.yaml").read_text()
        self.assertIn(
            "  sent_mail_hold_days_cold: 2            # elapsed 24-hour periods since Operator's latest actual sent email. Equality releases the hold\n"
            "  sent_mail_hold_days_active: 1          # same elapsed-time rule for an active Contact. Never compare date-only values\n",
            policy,
        )

    def test_channel_accounts_come_from_admission_instructions_and_missing_holds(self):
        text = (WORKFLOWS / "watch-sync/references/reconcile.md").read_text()
        step_three = next(line for line in text.splitlines() if line.startswith("3. "))
        self.assertIn("account list", step_three)
        self.assertIn("`admission_instructions`", step_three)
        self.assertIn("`pplx automation get`", step_three)
        self.assertIn("not checked, never an empty list", text)
        self.assertIn("Propose no Account-list changes for that watch", text)

    def test_identity_uses_the_approved_explained_superset_boundary(self):
        text = (WORKFLOWS / "interaction-sync/references/reconcile.md").read_text()
        self.assertIn("- For a Momentum transcript, before Extract", text)
        for sentence in (
            "Compare the meeting start instant with the Calendar event and account for every external Calendar attendee email in the transcript metadata.",
            "Accept an alternate address only when a read source verifies that it belongs to the same person.",
            "Additional transcript attendees alone do not disprove identity, but list their unmatched or blank emails and do not infer a Contact identity from a name.",
            "A conflicting attendee identity, conflicting start time or unexplained missing Calendar attendee makes the run needs-input.",
        ):
            self.assertIn(sentence, text)
        self.assertNotIn("They must match.", text)
        contract = (WORKFLOWS / "interaction-sync/CONTEXT.md").read_text()
        row = next(line for line in contract.splitlines() if line.startswith("| Identity,"))
        self.assertIn('`references/reconcile.md` "Find the interaction"', row)

    def test_first_cold_task_without_open_opportunity_stays_a_prospecting_blocker(self):
        text = (WORKFLOWS / "task-triage-speed-run/references/grouping.md").read_text()
        self.assertIn("A first cold email on a Task with no open Opportunity belongs to Prospecting.", text)
        self.assertIn("Keep the Task visible as a handoff blocker", text)
        self.assertIn("A recipient requires a verified address Operator sent to without a bounce.", text)
        self.assertIn("This is the only exception to the verified-recipient gate.", text)

    def test_triage_runs_the_timestamp_hold_for_preparation_and_creation(self):
        references = WORKFLOWS / "task-triage-speed-run/references"
        for filename in ("collect", "grouping", "drafts"):
            with self.subTest(reference=filename):
                text = (references / f"{filename}.md").read_text()
                self.assertIn("--send-hold", text)
        grouping = (references / "grouping.md").read_text()
        self.assertIn("send_hold_active", grouping)
        self.assertIn("send_hold_cold", grouping)
        self.assertIn("never the date-only `last_sent`", grouping)


if __name__ == "__main__":
    unittest.main()
