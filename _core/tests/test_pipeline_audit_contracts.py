"""Regressions for the Pipeline audit's bounded loading and evidence rules."""
from pathlib import Path
import unittest

from test_skill_contracts import loaded_contract_text


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline/workflows"


class PipelineAuditContracts(unittest.TestCase):
    def test_pipeline_review_loads_triage_shape_and_future_task_exclusion(self):
        loaded = loaded_contract_text(PIPELINE / "pipeline-review")
        self.assertIn("## Triage findings", loaded)
        self.assertIn("Future Tasks never enter these triage findings", loaded)

    def test_interaction_loads_per_record_approval_grammar(self):
        loaded = loaded_contract_text(PIPELINE / "interaction-sync")
        self.assertIn("number them E1, E2 or F1, F2 and approve each on its own", loaded)
        self.assertIn("Each approval covers one record", loaded)

    def test_next_step_outbound_requires_exact_action_evidence(self):
        text = (PIPELINE / "task-triage-speed-run/references/next-steps.md").read_text()
        self.assertNotIn("the stored action is done, so", text)
        self.assertIn("only when that exact sent message fulfilled the stored action", text)
        self.assertIn("Otherwise retain the stored action", text)

    def test_sweep_checks_both_stable_markers_without_creator_cutoff(self):
        text = (PIPELINE / "interaction-sync/references/sweep.md").read_text()
        self.assertIn("policy.salesforce.calendar_call_marker", text)
        self.assertIn("regardless of creator or creation date", text)
        self.assertNotIn("held policy PR", text)

    def test_sweep_watch_and_customer_review_use_ownership_helper(self):
        for workflow, reference in (("interaction-sync", "sweep"), ("watch-sync", "reconcile"), ("customer-review", "collect")):
            with self.subTest(workflow=workflow):
                text = (PIPELINE / workflow / f"references/{reference}.md").read_text()
                self.assertNotIn("pplx project sessions list --search", text)
                self.assertIn("deal_thread_match", text)
                self.assertIn('"Account session search"', (PIPELINE / workflow / "CONTEXT.md").read_text())

    def test_stale_trigger_text_matches_hygiene_check_activity_semantics(self):
        triggers = (ROOT / "workspaces/pipeline/references/triggers.md").read_text()
        self.assertNotIn("no Task or Event within `policy.pipeline.stale_days`", triggers)
        self.assertIn("no completed Task or timestamped elapsed Event within `policy.pipeline.stale_days`", triggers)
        self.assertIn("Open Tasks and date-only (timing-unknown) Events never count as activity.", triggers)
        helper = (ROOT / "_core/scripts/hygiene_check.py").read_text()
        self.assertIn('and a["kind"] != "open_task"', helper)
        self.assertIn('(a["kind"] != "event" or a["timing"] == "elapsed")', helper)
        self.assertNotIn("Deviation from the stale policy text", helper)
        self.assertIn("A date-only (timing-unknown) Event and an open Task never count as\nactivity", helper)

    def test_watch_inventory_names_its_runtime_evidence_location(self):
        text = (PIPELINE / "watch-sync/references/reconcile.md").read_text()
        self.assertIn("invoking automation's current prompt", text)
        self.assertIn("Operator-approved source-thread evidence", text)

    def test_absent_watch_account_condition_is_not_an_empty_list(self):
        text = (PIPELINE / "watch-sync/references/reconcile.md").read_text()
        self.assertIn("not checked, never an empty list", text)
        self.assertIn("Propose no Account-list changes for that watch", text)

    def test_pilot_pdf_uses_verified_repo_and_sandbox(self):
        text = (PIPELINE / "pilot-usage/references/pdf-format.md").read_text()
        self.assertNotIn("Run from the Project Files checkout", text)
        self.assertIn("verified Project Files checkout", text)
        self.assertIn("absolute sandbox paths", text)

    def test_interaction_uses_policy_amount_source_vocabulary(self):
        loaded = loaded_contract_text(PIPELINE / "interaction-sync")
        self.assertNotIn("Matt_stated", loaded)
        self.assertIn("user_supplied", loaded)

    def test_null_account_contact_is_ambiguous_not_invented_linkage(self):
        text = (PIPELINE / "interaction-sync/references/reconcile.md").read_text()
        self.assertIn("null AccountId", text)

    def test_interaction_followup_without_open_opportunity_needs_input(self):
        text = (PIPELINE / "interaction-sync/references/proposals.md").read_text()
        self.assertIn("With no open Opportunity, C is needs-input", text)

    def test_invitation_thread_is_not_automatically_followup_thread(self):
        text = (PIPELINE / "interaction-sync/references/reconcile.md").read_text()
        self.assertIn("Exclude draft and automated calendar-notification messages", text)
        self.assertIn("newest eligible retrieved thread", text)

    def test_unbounded_call_requests_use_existing_calendar_windows(self):
        for workflow, reference, request in (
            ("sales-call-prep", "collect", 'For "next external call"'),
            ("interaction-sync", "reconcile", 'For "most recent external call"'),
        ):
            with self.subTest(workflow=workflow):
                text = (PIPELINE / workflow / f"references/{reference}.md").read_text()
                self.assertIn(request, text)
                self.assertIn("policy.tooling.calendar_", text)
                self.assertIn("run start", text)

    def test_brief_length_covers_every_call_type(self):
        text = (PIPELINE / "sales-call-prep/references/brief-formats.md").read_text()
        self.assertIn("up to 600 for discovery, demo, proposal or customer", text)

    def test_closed_deal_due_tasks_remain_visible_without_invented_completion(self):
        text = (PIPELINE / "task-triage-speed-run/references/grouping.md").read_text()
        self.assertIn("Closed Won or Closed Lost", text)
        self.assertIn("closing the Opportunity alone is not completion evidence", text)

    def test_triage_only_findings_do_not_need_deal_context_delivery(self):
        text = (PIPELINE / "pipeline-review/references/collect.md").read_text()
        self.assertIn("For a triage-only finding, keep the flagged deal in `deals`", text)

    def test_stale_helper_caller_and_weekly_backlog_note(self):
        catalog = (ROOT / "_core/scripts/CONTEXT.md").read_text()
        backlog = (ROOT / "_core/CONVENTIONS.md").read_text()
        self.assertIn("Forecast weekly and Monday tracking automations", catalog)
        self.assertNotIn("between daily pipeline reviews", backlog)
        self.assertNotIn("Item 11 keeps this list current", backlog)
        notification = (PIPELINE / "pipeline-review/references/report-format.md").read_text().split("## Notification\n", 1)[1]
        self.assertIn("- Every authorized scheduled run: always one in-app notification.", notification)
        self.assertNotIn("Every weekly or requested run", notification)


if __name__ == "__main__":
    unittest.main()
